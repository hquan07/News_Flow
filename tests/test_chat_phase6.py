from copy import deepcopy
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from bson import ObjectId
from fastapi import HTTPException
from httpx import AsyncClient
import httpx

from api.models.chat_actions import ActionConfirmRequest, ActionPreviewRequest
from api.security import create_access_token, permissions_for_role
from api.services import chat_actions, chat_guard


class Collection:
    def __init__(self):
        self.documents = []

    async def create_index(self, *args, **kwargs):
        return None

    async def insert_one(self, document):
        stored = deepcopy(document)
        stored.setdefault("_id", ObjectId())
        self.documents.append(stored)
        return SimpleNamespace(inserted_id=stored["_id"])

    @staticmethod
    def matches(document, query):
        for key, wanted in query.items():
            actual = document.get(key)
            if isinstance(wanted, dict):
                if "$gt" in wanted and not actual > wanted["$gt"]:
                    return False
            elif actual != wanted:
                return False
        return True

    async def find_one(self, query):
        return next((deepcopy(doc) for doc in self.documents if self.matches(doc, query)), None)

    async def find_one_and_update(self, query, update, return_document=None):
        for doc in self.documents:
            if self.matches(doc, query):
                doc.update(update["$set"])
                return deepcopy(doc)
        return None

    async def update_one(self, query, update, upsert=False):
        for doc in self.documents:
            if self.matches(doc, query):
                doc.update(update["$set"])
                return SimpleNamespace(matched_count=1)
        if upsert:
            self.documents.append({**query, **update.get("$set", {}), **update.get("$setOnInsert", {})})
        return SimpleNamespace(matched_count=0)


@pytest.fixture
def action_db(monkeypatch):
    database = SimpleNamespace(
        chat_action_requests=Collection(), chat_reports=Collection(), audit_logs=Collection(),
    )
    monkeypatch.setattr(chat_actions, "get_mongo_db", lambda: database)

    async def inline_to_thread(function, *args, **kwargs):
        return function(*args, **kwargs)

    monkeypatch.setattr(chat_actions.asyncio, "to_thread", inline_to_thread)

    async def no_limit(owner_id):
        return None

    monkeypatch.setattr(chat_guard, "check_rate_limit", no_limit)
    return database


def actor(role="operator", sub="alice"):
    return {"sub": sub, "role": role, "permissions": permissions_for_role(role)}


def headers(role="operator", sub="alice"):
    return {"Authorization": f"Bearer {create_access_token({'sub': sub, 'role': role})}"}


@pytest.mark.asyncio
async def test_preview_denied_before_pending_action(async_client: AsyncClient, action_db):
    response = await async_client.post(
        "/api/v1/chat/actions/preview",
        json={"action": "trigger_crawler", "spider_name": "vnexpress"},
        headers=headers("user"),
    )
    assert response.status_code == 403
    assert action_db.chat_action_requests.documents == []
    assert action_db.audit_logs.documents == []


@pytest.mark.asyncio
async def test_crawler_confirmation_is_owner_bound_single_use_and_allowlisted(
    async_client: AsyncClient, action_db, monkeypatch
):
    called = []

    async def fake_airflow(path, json_body):
        called.append((path, json_body))
        return {"dag_run_id": json_body["dag_run_id"], "state": "queued"}

    monkeypatch.setattr(chat_actions.crawler_admin, "_airflow_post", fake_airflow)
    bad = await async_client.post(
        "/api/v1/chat/actions/preview",
        json={"action": "trigger_crawler", "spider_name": "all"},
        headers=headers(),
    )
    assert bad.status_code == 422
    preview = await async_client.post(
        "/api/v1/chat/actions/preview",
        json={"action": "trigger_crawler", "spider_name": "vnexpress"},
        headers=headers(),
    )
    assert preview.status_code == 200
    data = preview.json()
    assert "vnexpress" in data["summary"]
    payload = {"action_id": data["action_id"], "confirmation_token": data["confirmation_token"], "confirm": True}
    assert (await async_client.post("/api/v1/chat/actions/confirm", json=payload, headers=headers(sub="bob"))).status_code == 404
    assert (await async_client.post("/api/v1/chat/actions/confirm", json={**payload, "confirmation_token": "x" * 43}, headers=headers())).status_code == 404
    assert (await async_client.post("/api/v1/chat/actions/confirm", json=payload, headers=headers("user"))).status_code == 403
    assert called == []
    done = await async_client.post("/api/v1/chat/actions/confirm", json=payload, headers=headers())
    assert done.status_code == 200
    assert done.json()["status"] == "succeeded"
    assert called[0][1]["conf"] == {"spider": "vnexpress"}
    assert called[0][1]["dag_run_id"] == f"chat__{data['action_id']}"
    assert (await async_client.post("/api/v1/chat/actions/confirm", json=payload, headers=headers())).status_code == 409
    assert len(called) == 1
    assert (await async_client.get(f"/api/v1/chat/actions/{data['action_id']}", headers=headers(sub="bob"))).status_code == 404
    status = await async_client.get(f"/api/v1/chat/actions/{data['action_id']}", headers=headers())
    assert status.json()["status"] == "succeeded"
    assert status.json()["result"]["dag_run_id"] == f"chat__{data['action_id']}"
    assert [item["action"] for item in action_db.audit_logs.documents] == [
        "chat.action_previewed", "chat.action_started", "chat.action_succeeded"
    ]
    assert data["confirmation_token"] not in str(action_db.audit_logs.documents)


@pytest.mark.asyncio
async def test_expired_action_and_missing_explicit_confirmation(action_db, monkeypatch):
    preview = await chat_actions.preview(
        ActionPreviewRequest(action="trigger_crawler", spider_name="tuoitre"), actor()
    )
    item = action_db.chat_action_requests.documents[0]
    item["expires_at"] = datetime.now(timezone.utc) - timedelta(seconds=1)
    with pytest.raises(HTTPException) as error:
        await chat_actions.confirm(ActionConfirmRequest(
            action_id=preview["action_id"], confirmation_token=preview["confirmation_token"], confirm=True
        ), actor())
    assert error.value.status_code == 410
    assert (await chat_actions.action_status(preview["action_id"], actor()))["status"] == "expired"
    with pytest.raises(Exception):
        ActionConfirmRequest(action_id=preview["action_id"], confirmation_token=preview["confirmation_token"], confirm=False)


@pytest.mark.asyncio
async def test_alert_acknowledgement_rechecks_active_alert(action_db, monkeypatch):
    monkeypatch.setattr(chat_actions, "get_alerts", lambda **kwargs: [{"alert_id": "volume:2026100108"}])
    updated = []

    async def fake_state(user_id, alert_id, acknowledged):
        updated.append((user_id, alert_id, acknowledged))
        return {"acknowledged": True}

    monkeypatch.setattr(chat_actions, "update_alert_state", fake_state)
    preview = await chat_actions.preview(
        ActionPreviewRequest(action="acknowledge_alert", alert_id="volume:2026100108"), actor()
    )
    result = await chat_actions.confirm(ActionConfirmRequest(
        action_id=preview["action_id"], confirmation_token=preview["confirmation_token"], confirm=True
    ), actor())
    assert result["result"]["acknowledged"] is True
    assert updated == [("alice", "volume:2026100108", True)]


@pytest.mark.asyncio
async def test_report_is_owner_scoped_bounded_and_csv_safe(
    async_client: AsyncClient, action_db, monkeypatch
):
    queries = []

    def fake_query(sql, params):
        queries.append((sql, params))
        return [{"source": "=cmd", "category": "@formula", "article_count": 3}]

    monkeypatch.setattr(chat_actions, "_query", fake_query)
    preview = await async_client.post(
        "/api/v1/chat/actions/preview",
        json={"action": "generate_report", "time_range": "7d", "source": "vnexpress"},
        headers=headers("user"),
    )
    assert preview.status_code == 200
    data = preview.json()
    done = await async_client.post(
        "/api/v1/chat/actions/confirm",
        json={"action_id": data["action_id"], "confirmation_token": data["confirmation_token"], "confirm": True},
        headers=headers("user"),
    )
    assert done.status_code == 200
    assert "LIMIT 50" in queries[0][0]
    assert "source = {source:String}" in queries[0][0]
    assert queries[0][1] == {"source": "vnexpress"}
    path = done.json()["result"]["download_url"]
    assert (await async_client.get(path, headers=headers("user", "bob"))).status_code == 404
    response = await async_client.get(path, headers=headers("user"))
    assert response.status_code == 200
    assert "'=cmd" in response.text
    assert "'@formula" in response.text
    assert "=cmd" not in response.text.replace("'=cmd", "")


@pytest.mark.asyncio
async def test_failed_crawler_action_is_not_replayed(action_db, monkeypatch):
    calls = []

    async def unavailable(path, json_body):
        calls.append(json_body["dag_run_id"])
        raise HTTPException(status_code=503, detail="Airflow unavailable")

    monkeypatch.setattr(chat_actions.crawler_admin, "_airflow_post", unavailable)
    preview = await chat_actions.preview(
        ActionPreviewRequest(action="trigger_crawler", spider_name="dantri"), actor()
    )
    confirmation = ActionConfirmRequest(
        action_id=preview["action_id"], confirmation_token=preview["confirmation_token"], confirm=True
    )
    with pytest.raises(HTTPException) as error:
        await chat_actions.confirm(confirmation, actor())
    assert error.value.status_code == 503
    assert action_db.chat_action_requests.documents[0]["status"] == "failed"
    with pytest.raises(HTTPException) as replay:
        await chat_actions.confirm(confirmation, actor())
    assert replay.value.status_code == 409
    assert len(calls) == 1
    assert action_db.audit_logs.documents[-1]["action"] == "chat.action_failed"


@pytest.mark.asyncio
async def test_audit_failure_prevents_external_side_effect(action_db, monkeypatch):
    preview = await chat_actions.preview(
        ActionPreviewRequest(action="trigger_crawler", spider_name="laodong"), actor()
    )

    async def broken_audit(event, actor_value, action_id, action):
        raise RuntimeError("audit unavailable")

    async def forbidden_airflow(*args, **kwargs):
        pytest.fail("Airflow called without audit")

    monkeypatch.setattr(chat_actions, "_audit", broken_audit)
    monkeypatch.setattr(chat_actions.crawler_admin, "_airflow_post", forbidden_airflow)
    with pytest.raises(RuntimeError):
        await chat_actions.confirm(ActionConfirmRequest(
            action_id=preview["action_id"], confirmation_token=preview["confirmation_token"], confirm=True
        ), actor())
    assert action_db.chat_action_requests.documents[0]["status"] == "failed"


@pytest.mark.asyncio
async def test_airflow_timeout_is_explicit_and_not_replayed(action_db, monkeypatch):
    async def timeout(path, json_body):
        raise httpx.ReadTimeout("timed out")

    monkeypatch.setattr(chat_actions.crawler_admin, "_airflow_post", timeout)
    preview = await chat_actions.preview(
        ActionPreviewRequest(action="trigger_crawler", spider_name="tuoitre"), actor()
    )
    with pytest.raises(HTTPException) as error:
        await chat_actions.confirm(ActionConfirmRequest(
            action_id=preview["action_id"], confirmation_token=preview["confirmation_token"], confirm=True
        ), actor())
    assert error.value.status_code == 503
    assert f"chat__{preview['action_id']}" in error.value.detail
    assert (await chat_actions.action_status(preview["action_id"], actor()))["status"] == "failed"
