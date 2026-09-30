from datetime import datetime, timezone

import pytest
from httpx import AsyncClient

from api.security import create_access_token
from api.services import alert_state


def _admin_headers():
    token = create_access_token(
        {"sub": "admin-user", "email": "admin@example.com", "role": "admin"}
    )
    return {"Authorization": f"Bearer {token}"}


class _StateCursor:
    def __init__(self, documents):
        self.documents = documents

    async def to_list(self, length):
        return self.documents[:length]


class _StateCollection:
    def __init__(self):
        self.documents = {}

    async def update_one(self, query, update, upsert=False):
        document = self.documents.get(query["_id"], {"_id": query["_id"]})
        document.update(update.get("$setOnInsert", {}))
        document.update(update.get("$set", {}))
        self.documents[query["_id"]] = document

    async def find_one(self, query, _projection=None):
        document = self.documents.get(query["_id"])
        if not document:
            return None
        return {key: value for key, value in document.items() if key != "_id"}

    def find(self, query, _projection=None):
        ids = set(query["alert_id"]["$in"])
        documents = [
            {key: value for key, value in document.items() if key != "_id"}
            for document in self.documents.values()
            if document["user_id"] == query["user_id"]
            and document["alert_id"] in ids
        ]
        return _StateCursor(documents)


class _StateDb:
    def __init__(self):
        self.alert_states = _StateCollection()


@pytest.mark.asyncio
async def test_alert_state_service_round_trip(monkeypatch):
    database = _StateDb()
    monkeypatch.setattr(alert_state, "get_mongo_db", lambda: database)

    saved = await alert_state.update_alert_state(
        "admin-user",
        "cluster:reddit_vn:unlabelled",
        pinned=True,
    )
    states = await alert_state.get_alert_states(
        "admin-user",
        ["cluster:reddit_vn:unlabelled"],
    )

    assert saved["pinned"] is True
    assert states[0]["alert_id"] == "cluster:reddit_vn:unlabelled"
    assert states[0]["pinned"] is True


@pytest.mark.asyncio
async def test_alert_state_query_requires_admin(async_client: AsyncClient):
    response = await async_client.post(
        "/api/v1/alerts/state/query",
        headers={"Authorization": ""},
        json={"alert_ids": ["viral:post-1"]},
    )

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_alert_state_query_is_scoped_to_authenticated_user(
    async_client: AsyncClient,
    monkeypatch,
):
    captured = {}

    async def fake_get_states(user_id, alert_ids):
        captured["user_id"] = user_id
        captured["alert_ids"] = alert_ids
        now = datetime.now(timezone.utc)
        return [
            {
                "alert_id": "viral:post-1",
                "user_id": user_id,
                "pinned": True,
                "acknowledged": False,
                "created_at": now,
                "updated_at": now,
            }
        ]

    monkeypatch.setattr("api.routers.alerts.get_alert_states", fake_get_states)

    response = await async_client.post(
        "/api/v1/alerts/state/query",
        json={"alert_ids": ["viral:post-1"]},
        headers=_admin_headers(),
    )

    assert response.status_code == 200
    assert captured == {
        "user_id": "admin-user",
        "alert_ids": ["viral:post-1"],
    }
    assert response.json()[0]["pinned"] is True


@pytest.mark.asyncio
async def test_patch_alert_state_persists_requested_field(
    async_client: AsyncClient,
    monkeypatch,
):
    captured = {}

    async def fake_update(user_id, alert_id, pinned=None, acknowledged=None):
        captured.update(
            user_id=user_id,
            alert_id=alert_id,
            pinned=pinned,
            acknowledged=acknowledged,
        )
        now = datetime.now(timezone.utc)
        return {
            "alert_id": alert_id,
            "user_id": user_id,
            "pinned": bool(pinned),
            "acknowledged": bool(acknowledged),
            "created_at": now,
            "updated_at": now,
        }

    monkeypatch.setattr("api.routers.alerts.update_alert_state", fake_update)

    response = await async_client.patch(
        "/api/v1/alerts/state/viral%3Apost-1",
        json={"acknowledged": True},
        headers=_admin_headers(),
    )

    assert response.status_code == 200
    assert captured == {
        "user_id": "admin-user",
        "alert_id": "viral:post-1",
        "pinned": None,
        "acknowledged": True,
    }
    assert response.json()["acknowledged"] is True


@pytest.mark.asyncio
async def test_patch_alert_state_rejects_empty_update(async_client: AsyncClient):
    response = await async_client.patch(
        "/api/v1/alerts/state/viral%3Apost-1",
        json={},
        headers=_admin_headers(),
    )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_interaction_trend_endpoint(async_client: AsyncClient, monkeypatch):
    monkeypatch.setattr(
        "api.routers.alerts.get_interaction_trend",
        lambda source=None, granularity="15m": {
            "source": source,
            "granularity": granularity,
            "data": [
                {
                    "bucket": datetime(2026, 9, 28, 10, 0),
                    "interactions": 120,
                    "post_count": 4,
                }
            ],
        },
    )

    response = await async_client.get(
        "/api/v1/alerts/social/trends?source=reddit_vn&granularity=1h"
    )

    assert response.status_code == 200
    assert response.json()["source"] == "reddit_vn"
    assert response.json()["data"][0]["interactions"] == 120
