import asyncio
from copy import deepcopy
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from httpx import AsyncClient

from api.security import create_access_token
from api.routers import retention as retention_router
from api.services import operations, retention, source_config, workspace_store
from tests.test_chat_foundation import _Collection


class UpsertCollection(_Collection):
    async def update_one(self, query, update, upsert=False):
        result = await super().update_one(query, update)
        if result.matched_count or not upsert:
            return result
        document = {**deepcopy(query), **deepcopy(update["$set"])}
        await self.insert_one(document)
        return SimpleNamespace(matched_count=0, upserted_id=self.documents[-1]["_id"])


def headers(subject: str, email: str, role: str = "user") -> dict[str, str]:
    token = create_access_token({"sub": subject, "email": email, "role": role})
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_source_settings_are_persisted_as_overrides(monkeypatch):
    database = SimpleNamespace(source_settings=UpsertCollection())
    monkeypatch.setattr(source_config, "get_mongo_db", lambda: database)
    result = await source_config.update("vnexpress", {"enabled": False, "rate_limit_seconds": 5}, "operator")
    assert result["enabled"] is False
    assert (await source_config.settings_map())["vnexpress"]["rate_limit_seconds"] == 5


def test_article_lineage_reports_missing_and_complete_stages(monkeypatch):
    now = datetime.now(timezone.utc)
    monkeypatch.setattr(operations, "_query", lambda *_args, **_kwargs: [{
        "article_id": "a", "title": "Article", "source": "one", "url": "https://example.com/a",
        "crawled_at": now, "loaded_at": now, "keywords_at": now, "entities_at": None, "sentiment_at": now,
    }])
    result = operations.article_lineage("a")
    assert result["complete"] is False
    assert next(stage for stage in result["stages"] if stage["stage"] == "entities")["status"] == "missing"


@pytest.mark.asyncio
async def test_retention_policy_is_disabled_until_configured(monkeypatch):
    database = SimpleNamespace(retention_policies=UpsertCollection())
    monkeypatch.setattr(retention, "get_mongo_db", lambda: database)
    monkeypatch.setattr(retention, "_query", lambda sql, params=None: (
        [{"table": "raw_articles", "rows": 100, "bytes_on_disk": 1024}]
        if "system.parts" in sql else [{"rows_to_delete": 25}]
    ))
    initial = await retention.list_policies()
    articles = next(item for item in initial["datasets"] if item["dataset"] == "articles")
    assert articles["enabled"] is False
    await retention.update_policy("articles", 90, True, "operator")
    preview = await retention.preview("articles")
    assert preview == {"dataset": "articles", "retention_days": 90, "rows_to_delete": 25, "enabled": True}


def test_disabled_retention_policy_cannot_be_applied(monkeypatch):
    async def preview(_dataset: str):
        return {"dataset": "articles", "retention_days": 365, "rows_to_delete": 25, "enabled": False}

    async def unexpected_airflow_call(*_args, **_kwargs):
        raise AssertionError("Airflow must not be called for a disabled retention policy")

    monkeypatch.setattr(retention_router.retention, "preview", preview)
    monkeypatch.setattr(retention_router.crawler_admin, "_airflow_post", unexpected_airflow_call)

    async def apply_disabled_policy():
        return await retention_router.apply_policy(
            "articles",
            retention_router.RetentionApply(confirm=True),
            {"sub": "operator"},
        )

    with pytest.raises(retention_router.HTTPException) as raised:
        asyncio.run(apply_disabled_policy())

    assert raised.value.status_code == 409
    assert raised.value.detail == "Enable and save this retention policy before applying it"


@pytest.fixture
def workspace_db(monkeypatch):
    database = SimpleNamespace(team_workspaces=_Collection(), workspace_resources=_Collection())
    monkeypatch.setattr(workspace_store, "get_mongo_db", lambda: database)
    return database


@pytest.mark.asyncio
async def test_team_workspace_roles_and_shared_watchlists(async_client: AsyncClient, workspace_db):
    owner = headers("alice", "alice@example.com")
    member = headers("bob", "bob@example.com")
    created = await async_client.post("/api/v1/workspaces", json={"name": "Newsroom"}, headers=owner)
    assert created.status_code == 201
    workspace_id = created.json()["id"]
    invited = await async_client.put(f"/api/v1/workspaces/{workspace_id}/members", json={"email": "bob@example.com", "role": "viewer"}, headers=owner)
    assert invited.status_code == 200
    assert len((await async_client.get("/api/v1/workspaces", headers=member)).json()) == 1
    denied = await async_client.post(f"/api/v1/workspaces/{workspace_id}/watchlists", json={"name": "AI", "kind": "keyword", "value": "AI"}, headers=member)
    assert denied.status_code == 403
    await async_client.put(f"/api/v1/workspaces/{workspace_id}/members", json={"email": "bob@example.com", "role": "editor"}, headers=owner)
    shared = await async_client.post(f"/api/v1/workspaces/{workspace_id}/watchlists", json={"name": "AI", "kind": "keyword", "value": "AI"}, headers=member)
    assert shared.status_code == 201
    assert (await async_client.get(f"/api/v1/workspaces/{workspace_id}/watchlists", headers=owner)).json()[0]["value"] == "AI"
    denied_delete = await async_client.delete(f"/api/v1/workspaces/{workspace_id}", headers=member)
    assert denied_delete.status_code == 403
    deleted = await async_client.delete(f"/api/v1/workspaces/{workspace_id}", headers=owner)
    assert deleted.status_code == 204
    assert (await async_client.get("/api/v1/workspaces", headers=owner)).json() == []
    assert workspace_db.workspace_resources.documents == []
