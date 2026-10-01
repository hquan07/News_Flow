"""Natural-language article counts must not fall through to latest-article lists."""

from types import SimpleNamespace

import pytest
from httpx import AsyncClient

from api.routers import chat
from api.security import create_access_token
from api.services import chat_guard, chat_metrics, chat_store, chat_tools
from tests.test_chat_foundation import _Collection


@pytest.fixture
def chat_db(monkeypatch):
    db = SimpleNamespace(
        chat_conversations=_Collection(),
        chat_messages=_Collection(),
        audit_logs=_Collection(),
    )
    monkeypatch.setattr(chat_store, "get_mongo_db", lambda: db)

    async def inline_tool(payload, actor, previous_context):
        return chat_tools.answer_question(payload, actor, previous_context)

    async def noop(*args, **kwargs):
        return None

    monkeypatch.setattr(chat, "_run_tool", inline_tool)
    monkeypatch.setattr(chat_guard, "check_rate_limit", noop)
    monkeypatch.setattr(chat_metrics, "record", noop)
    return db


def headers(role="user"):
    token = create_access_token({"sub": "alice", "role": role})
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_total_count_from_named_source_is_all_time_by_default(
    async_client: AsyncClient, chat_db, monkeypatch
):
    calls = []

    def fake_query(sql, params):
        calls.append((sql, params))
        return [{"article_count": 1234}]

    monkeypatch.setattr(chat_tools, "_query", fake_query)
    response = await async_client.post(
        "/api/v1/chat",
        json={"message": "tổng số bài báo thu thập được từ vnexpress"},
        headers=headers(),
    )
    assert response.status_code == 200
    data = response.json()
    assert data["tool"] == "count_articles"
    assert data["time_range"] == "all"
    assert "1.234 bài báo từ vnexpress" in data["answer"]
    assert "từ trước đến nay" in data["answer"]
    assert data["sources"] == []
    assert "count()" in calls[0][0]
    assert "ORDER BY" not in calls[0][0]
    assert "publish_time" not in calls[0][0]
    assert calls[0][1] == {"source": "vnexpress"}
    assert chat_db.chat_messages.documents[-1]["context"]["time_range"] == "all"
    assert chat_db.chat_messages.documents[-1]["context"]["source"] == "vnexpress"


@pytest.mark.asyncio
async def test_count_followup_changes_source_and_period(
    async_client: AsyncClient, chat_db, monkeypatch
):
    calls = []

    def fake_query(sql, params):
        calls.append((sql, params))
        return [{"article_count": 7}]

    monkeypatch.setattr(chat_tools, "_query", fake_query)
    first = await async_client.post(
        "/api/v1/chat", json={"message": "Tổng số bài báo từ VnExpress"}, headers=headers()
    )
    second = await async_client.post(
        "/api/v1/chat",
        json={"conversation_id": first.json()["conversation_id"], "message": "Còn Tuổi Trẻ trong 30 ngày qua?"},
        headers=headers(),
    )
    assert second.status_code == 200
    assert second.json()["tool"] == "count_articles"
    assert second.json()["time_range"] == "30d"
    assert "từ tuoitre" in second.json()["answer"]
    assert calls[1][1] == {"source": "tuoitre"}
    assert "30 DAY" in calls[1][0]


@pytest.mark.asyncio
async def test_article_listing_honors_source_mentioned_in_message(
    async_client: AsyncClient, chat_db, monkeypatch
):
    captured = {}

    def fake_query(sql, params):
        captured.update(params=params)
        return []

    monkeypatch.setattr(chat_tools, "_query", fake_query)
    response = await async_client.post(
        "/api/v1/chat", json={"message": "Tìm bài viết từ VnExpress"}, headers=headers()
    )
    assert response.status_code == 200
    assert response.json()["tool"] == "search_articles"
    assert captured["params"]["source"] == "vnexpress"


@pytest.mark.asyncio
async def test_count_respects_selected_period_and_topic(
    async_client: AsyncClient, chat_db, monkeypatch
):
    calls = []

    def fake_query(sql, params):
        calls.append((sql, params))
        return [{"article_count": 3}]

    monkeypatch.setattr(chat_tools, "_query", fake_query)
    response = await async_client.post(
        "/api/v1/chat",
        json={
            "message": "Có bao nhiêu bài báo về AI từ Tuổi Trẻ?",
            "time_range": "7d",
        },
        headers=headers(),
    )
    assert response.status_code == 200
    assert response.json()["time_range"] == "7d"
    assert "3 bài báo từ tuoitre có tiêu đề chứa 'AI' trong 7 ngày qua" in response.json()["answer"]
    assert "7 DAY" in calls[0][0]
    assert calls[0][1] == {"source": "tuoitre", "title_query": "%AI%"}


@pytest.mark.asyncio
async def test_count_requires_dashboard_permission_before_query(
    monkeypatch
):
    monkeypatch.setattr(chat_tools, "_query", lambda *args: pytest.fail("queried without permission"))
    # Direct tool contract: an actor without dashboard.read never reaches ClickHouse.
    from api.models.chat import ChatRequest
    from fastapi import HTTPException

    with pytest.raises(HTTPException) as error:
        chat_tools.answer_question(ChatRequest(message="Tổng số bài báo từ VnExpress"), {"permissions": []})
    assert error.value.status_code == 403
