from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from httpx import AsyncClient

from api.security import create_access_token
from api.routers import chat
from api.services import chat_store, chat_tools
from tests.test_chat_foundation import _Collection


@pytest.fixture
def chat_db(monkeypatch):
    database = SimpleNamespace(
        chat_conversations=_Collection(),
        chat_messages=_Collection(),
        audit_logs=_Collection(),
    )
    monkeypatch.setattr(chat_store, "get_mongo_db", lambda: database)
    return database


@pytest.fixture(autouse=True)
def inline_chat_tools(monkeypatch):
    async def run_tool(payload, actor):
        return chat_tools.answer_question(payload, actor)

    monkeypatch.setattr(chat, "_run_tool", run_tool)


def _headers(subject: str, role: str = "user"):
    token = create_access_token({"sub": subject, "role": role})
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_article_answer_has_real_sources_and_persisted_metadata(
    async_client: AsyncClient, chat_db, monkeypatch
):
    captured = {}

    def fake_query(sql, params):
        captured.update(sql=sql, params=params)
        return [{
            "article_id": "article-1",
            "title": "AI tại Việt Nam",
            "url": "https://example.com/ai",
            "source": "vnexpress",
            "published_at": datetime(2026, 10, 1, tzinfo=timezone.utc),
        }]

    monkeypatch.setattr(chat_tools, "_query", fake_query)
    response = await async_client.post(
        "/api/v1/chat",
        json={"message": "Tìm bài viết về AI", "source": "vnexpress", "time_range": "today"},
        headers=_headers("alice"),
    )
    assert response.status_code == 200
    data = response.json()
    assert data["tool"] == "search_articles"
    assert data["sources"][0]["url"] == "https://example.com/ai"
    assert data["queried_at"]
    assert captured["params"] == {"source": "vnexpress", "title_query": "%AI%"}
    assert "24 HOUR" in captured["sql"]
    assert "a.source = {source:String}" in captured["sql"]
    assert [item["role"] for item in chat_db.chat_messages.documents] == ["user", "assistant"]

    detail = await async_client.get(
        f"/api/v1/chat/conversations/{data['conversation_id']}", headers=_headers("alice")
    )
    assert detail.status_code == 200
    assert detail.json()["messages"][1]["sources"][0]["article_id"] == "article-1"


@pytest.mark.asyncio
async def test_user_alert_is_denied_before_data_access_or_persistence(
    async_client: AsyncClient, chat_db, monkeypatch
):
    def forbidden(*_args, **_kwargs):
        raise AssertionError("alert data queried before permission check")

    monkeypatch.setattr(chat_tools, "get_alerts", forbidden)
    response = await async_client.post(
        "/api/v1/chat", json={"message": "Có cảnh báo nào không?"},
        headers=_headers("alice"),
    )
    assert response.status_code == 403
    assert chat_db.chat_conversations.documents == []
    assert chat_db.chat_messages.documents == []


@pytest.mark.asyncio
async def test_existing_conversation_owner_is_checked_first(
    async_client: AsyncClient, chat_db, monkeypatch
):
    conversation = await chat_store.create_conversation("alice", "Private")

    def forbidden(*_args, **_kwargs):
        raise AssertionError("tool called before owner check")

    monkeypatch.setattr(chat_tools, "_query", forbidden)
    response = await async_client.post(
        "/api/v1/chat",
        json={"conversation_id": conversation["id"], "message": "Tin mới nhất"},
        headers=_headers("bob", "admin"),
    )
    assert response.status_code == 404
    assert chat_db.chat_messages.documents == []


@pytest.mark.asyncio
async def test_trending_query_is_bounded_and_parameterized(
    async_client: AsyncClient, chat_db, monkeypatch
):
    captured = {}

    def fake_query(sql, params):
        captured.update(sql=sql, params=params)
        return [{"keyword": "AI", "count": 12}]

    monkeypatch.setattr(chat_tools, "_query", fake_query)
    response = await async_client.post(
        "/api/v1/chat",
        json={"message": "Từ khóa nào thịnh hành?", "source": "vnexpress", "category": "tech"},
        headers=_headers("alice"),
    )
    assert response.status_code == 200
    assert "AI: 12 bài" in response.json()["answer"]
    assert "LIMIT 10" in captured["sql"]
    assert captured["params"] == {"source": "vnexpress", "category": "tech"}


@pytest.mark.asyncio
async def test_sentiment_uses_filtered_article_rows(
    async_client: AsyncClient, chat_db, monkeypatch
):
    captured = {}

    def fake_query(sql, params):
        captured.update(sql=sql, params=params)
        return [{"sentiment_label": "positive", "count": 3}]

    monkeypatch.setattr(chat_tools, "_query", fake_query)
    response = await async_client.post(
        "/api/v1/chat",
        json={"message": "Sentiment về AI trong 30 ngày qua", "time_range": "30d"},
        headers=_headers("alice"),
    )
    assert response.status_code == 200
    assert response.json()["tool"] == "get_sentiment_distribution"
    assert "positive: 3 bài" in response.json()["answer"]
    assert captured["params"] == {"title_query": "%AI%"}
    assert "raw_article_sentiment FINAL" in captured["sql"]
    assert "30 DAY" in captured["sql"]


@pytest.mark.asyncio
async def test_operator_can_read_alerts_but_filtered_alert_request_is_rejected(
    async_client: AsyncClient, chat_db, monkeypatch
):
    monkeypatch.setattr(chat_tools, "get_alerts", lambda **_kwargs: [
        {"hour_slot": "2026-10-01T08:00:00", "article_count": 20, "z_score": 2.5}
    ])
    headers = _headers("operator-1", "operator")
    response = await async_client.post(
        "/api/v1/chat", json={"message": "Có cảnh báo tăng đột biến không?"},
        headers=headers,
    )
    assert response.status_code == 200
    assert response.json()["tool"] == "get_volume_alerts"
    filtered = await async_client.post(
        "/api/v1/chat", json={"message": "Có cảnh báo không?", "source": "vnexpress"},
        headers=headers,
    )
    assert filtered.status_code == 422
    assert len(chat_db.chat_conversations.documents) == 1


@pytest.mark.asyncio
async def test_tool_failure_does_not_save_a_partial_question(
    async_client: AsyncClient, chat_db, monkeypatch
):
    def unavailable(*_args):
        raise RuntimeError("query failed")

    monkeypatch.setattr(chat_tools, "_query", unavailable)
    with pytest.raises(RuntimeError):
        await async_client.post(
            "/api/v1/chat", json={"message": "Tin mới nhất"},
            headers=_headers("alice"),
        )
    assert chat_db.chat_conversations.documents == []
    assert chat_db.chat_messages.documents == []


@pytest.mark.asyncio
async def test_stream_sends_answer_and_metadata(
    async_client: AsyncClient, chat_db, monkeypatch
):
    monkeypatch.setattr(chat_tools, "_query", lambda *_args: [])
    response = await async_client.post(
        "/api/v1/chat/stream",
        json={"message": "Tin mới nhất"},
        headers=_headers("alice"),
    )
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert "event: delta\n" in response.text
    assert "event: done\n" in response.text
    assert "conversation_id" in response.text


@pytest.mark.asyncio
async def test_unsupported_question_and_blank_message(
    async_client: AsyncClient, chat_db
):
    blank = await async_client.post(
        "/api/v1/chat", json={"message": "  "}, headers=_headers("alice")
    )
    assert blank.status_code == 422
    response = await async_client.post(
        "/api/v1/chat", json={"message": "Xin chào"}, headers=_headers("alice")
    )
    assert response.status_code == 200
    assert response.json()["tool"] is None
    assert response.json()["sources"] == []
