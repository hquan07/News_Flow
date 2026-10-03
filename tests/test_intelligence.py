from types import SimpleNamespace

import pytest
from httpx import AsyncClient

from api.security import create_access_token
from api.services import intelligence_store
from tests.test_chat_foundation import _Collection


@pytest.fixture
def intelligence_db(monkeypatch):
    database = SimpleNamespace(
        intelligence_watchlists=_Collection(),
        intelligence_alert_rules=_Collection(),
        intelligence_saved_queries=_Collection(),
    )
    monkeypatch.setattr(intelligence_store, "get_mongo_db", lambda: database)
    return database


def headers(subject: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token({'sub': subject, 'role': 'user'})}"}


@pytest.mark.asyncio
async def test_personal_intelligence_crud_is_owner_scoped(async_client: AsyncClient, intelligence_db):
    alice = headers("alice")
    bob = headers("bob")
    created = await async_client.post("/api/v1/intelligence/watchlists", json={
        "name": "  VinFast news  ", "kind": "entity", "value": "VinFast"
    }, headers=alice)
    assert created.status_code == 201
    item = created.json()
    assert item["name"] == "VinFast news"
    assert (await async_client.get("/api/v1/intelligence/watchlists", headers=bob)).json() == []
    assert (await async_client.patch(
        f"/api/v1/intelligence/watchlists/{item['id']}", json={"enabled": False}, headers=bob
    )).status_code == 404
    paused = await async_client.patch(
        f"/api/v1/intelligence/watchlists/{item['id']}", json={"enabled": False}, headers=alice
    )
    assert paused.json()["enabled"] is False
    assert (await async_client.delete(
        f"/api/v1/intelligence/watchlists/{item['id']}", headers=alice
    )).status_code == 204


@pytest.mark.asyncio
async def test_alert_rules_and_scheduled_queries(async_client: AsyncClient, intelligence_db):
    auth = headers("analyst")
    alert = await async_client.post("/api/v1/intelligence/alert-rules", json={
        "name": "AI spike", "kind": "keyword_volume", "target": "AI",
        "threshold": 25, "window_minutes": 60, "channels": ["dashboard"]
    }, headers=auth)
    assert alert.status_code == 201
    query = await async_client.post("/api/v1/intelligence/saved-queries", json={
        "name": "Morning AI", "query": "AI", "schedule": "daily"
    }, headers=auth)
    assert query.status_code == 201
    assert query.json()["next_run_at"] is not None
    assert len((await async_client.get("/api/v1/intelligence/alert-rules", headers=auth)).json()) == 1
    assert len((await async_client.get("/api/v1/intelligence/saved-queries", headers=auth)).json()) == 1


@pytest.mark.asyncio
async def test_saved_query_requires_a_filter(async_client: AsyncClient, intelligence_db):
    response = await async_client.post("/api/v1/intelligence/saved-queries", json={
        "name": "Empty", "query": "", "schedule": "none"
    }, headers=headers("alice"))
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_advanced_sentiment_filter(async_client: AsyncClient):
    response = await async_client.get("/api/v1/articles?sentiment=positive")
    assert response.status_code == 200
    assert [item["article_id"] for item in response.json()["data"]] == ["hash_test_1"]
