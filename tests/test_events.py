from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from httpx import AsyncClient

from api.models.chat import ChatRequest
from api.security import create_access_token
from api.services import chat_tools, crisis_store, event_clustering
from tests.test_chat_foundation import _Collection


ARTICLES = [
    {"article_id": "a1", "title": "VinFast ra mắt mẫu xe điện mới tại Việt Nam", "url": "https://example.com/a1", "source": "vnexpress", "category": "tech", "published_at": datetime(2026, 10, 1, 8, tzinfo=timezone.utc)},
    {"article_id": "a2", "title": "VinFast ra mắt xe điện mới ở Việt Nam", "url": "https://example.com/a2", "source": "tuoitre", "category": "tech", "published_at": datetime(2026, 10, 1, 9, tzinfo=timezone.utc)},
    {"article_id": "a3", "title": "Mẫu xe điện VinFast mới chính thức ra mắt", "url": "https://example.com/a3", "source": "thanhnien", "category": "tech", "published_at": datetime(2026, 10, 1, 10, tzinfo=timezone.utc)},
    {"article_id": "b1", "title": "Đội tuyển Việt Nam chuẩn bị trận đấu", "url": "https://example.com/b1", "source": "vnexpress", "category": "sports", "published_at": datetime(2026, 10, 1, 11, tzinfo=timezone.utc)},
]


@pytest.fixture
def clustered(monkeypatch):
    monkeypatch.setattr(event_clustering, "_load_articles", lambda _days, _limit: ARTICLES)
    return event_clustering.cluster_events()


@pytest.fixture
def crisis_db(monkeypatch):
    database = SimpleNamespace(crisis_rooms=_Collection())
    monkeypatch.setattr(crisis_store, "get_mongo_db", lambda: database)
    return database


def headers(subject: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token({'sub': subject, 'role': 'user'})}"}


def test_event_clustering_detects_related_and_duplicate_articles(clustered):
    assert len(clustered) == 1
    assert clustered[0]["article_count"] == 3
    assert clustered[0]["duplicate_count"] >= 1
    assert clustered[0]["sources"] == ["thanhnien", "tuoitre", "vnexpress"]


def test_chat_can_answer_in_event_context(clustered, monkeypatch):
    event = clustered[0]
    monkeypatch.setattr(chat_tools, "event_detail", lambda *_args, **_kwargs: event)
    result = chat_tools.answer_question(
        ChatRequest(message="Tóm tắt sự kiện này", event_id=event["event_id"]),
        {"permissions": ["dashboard.read"]},
    )
    assert result.tool == "event_context"
    assert result.context["event_id"] == event["event_id"]
    assert len(result.sources) == 3


@pytest.mark.asyncio
async def test_crisis_rooms_are_owner_scoped(async_client: AsyncClient, crisis_db, clustered, monkeypatch):
    event = clustered[0]
    monkeypatch.setattr(event_clustering, "event_detail", lambda *_args, **_kwargs: event)
    created = await async_client.post("/api/v1/events/rooms", json={
        "event_id": event["event_id"], "name": "VinFast launch", "notes": "Monitor coverage"
    }, headers=headers("alice"))
    assert created.status_code == 201
    room_id = created.json()["id"]
    assert (await async_client.get("/api/v1/events/rooms/mine", headers=headers("bob"))).json() == []
    updated = await async_client.patch(
        f"/api/v1/events/rooms/{room_id}", json={"status": "active"}, headers=headers("alice")
    )
    assert updated.json()["status"] == "active"
    assert (await async_client.delete(
        f"/api/v1/events/rooms/{room_id}", headers=headers("bob")
    )).status_code == 404
