from types import SimpleNamespace

import pytest
from httpx import AsyncClient

from api.routers import chat
from api.security import create_access_token
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
    async def run_tool(payload, actor, previous_context):
        return chat_tools.answer_question(payload, actor, previous_context)

    monkeypatch.setattr(chat, "_run_tool", run_tool)


def _headers(subject: str, role: str = "user"):
    token = create_access_token({"sub": subject, "role": role})
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_followup_reuses_subject_and_requeries_new_time_window(
    async_client: AsyncClient, chat_db, monkeypatch
):
    calls = []

    def fake_query(sql, params):
        calls.append((sql, params))
        return [{
            "article_id": "a1",
            "title": "AI tại Việt Nam",
            "url": "https://example.com/a1",
            "source": "vnexpress",
            "published_at": None,
        }]

    monkeypatch.setattr(chat_tools, "_query", fake_query)
    first = await async_client.post(
        "/api/v1/chat", json={"message": "Tìm bài viết về AI"},
        headers=_headers("alice"),
    )
    assert first.status_code == 200
    second = await async_client.post(
        "/api/v1/chat",
        json={"conversation_id": first.json()["conversation_id"], "message": "Còn 30 ngày qua?"},
        headers=_headers("alice"),
    )
    assert second.status_code == 200
    assert second.json()["tool"] == "search_articles"
    assert second.json()["time_range"] == "30d"
    assert "30 DAY" in calls[1][0]
    assert calls[1][1]["title_query"] == "%AI%"
    assert len(chat_db.chat_messages.documents) == 4
    assert chat_db.chat_messages.documents[-1]["context"]["query"] == "AI"


@pytest.mark.asyncio
async def test_source_comparison_uses_selected_sources_and_chart(
    async_client: AsyncClient, chat_db, monkeypatch
):
    captured = {}

    def fake_query(sql, params):
        captured.update(sql=sql, params=params)
        return [
            {"source": "vnexpress", "article_count": 12, "avg_word_count": 400},
            {"source": "tuoitre", "article_count": 8, "avg_word_count": 350},
        ]

    monkeypatch.setattr(chat_tools, "_query", fake_query)
    response = await async_client.post(
        "/api/v1/chat",
        json={"message": "So sánh nguồn VnExpress và Tuổi Trẻ"},
        headers=_headers("alice"),
    )
    assert response.status_code == 200
    assert response.json()["tool"] == "compare_sources"
    assert captured["params"]["source_names"] == ["vnexpress", "tuoitre"]
    assert "has({source_names:Array(String)}, a.source)" in captured["sql"]
    assert response.json()["chart"]["points"][0] == {"label": "vnexpress", "value": 12.0}
    detail = await async_client.get(
        f"/api/v1/chat/conversations/{response.json()['conversation_id']}",
        headers=_headers("alice"),
    )
    assert detail.json()["messages"][-1]["chart"]["title"] == "Số bài theo nguồn"


@pytest.mark.asyncio
async def test_entity_cooccurrence_is_labeled_as_such(
    async_client: AsyncClient, chat_db, monkeypatch
):
    captured = {}

    def fake_query(sql, params):
        captured.update(sql=sql, params=params)
        return [{"entity_name": "Hà Nội", "entity_type": "LOC", "article_count": 3}]

    monkeypatch.setattr(chat_tools, "_query", fake_query)
    response = await async_client.post(
        "/api/v1/chat",
        json={"message": "Thực thể nào liên quan đến VinFast?"},
        headers=_headers("alice"),
    )
    assert response.status_code == 200
    assert response.json()["tool"] == "get_entities"
    assert captured["params"]["entity_query"] == "%VinFast%"
    assert "countDistinct(a.url_hash)" in captured["sql"]
    assert "không chứng minh quan hệ trực tiếp" in response.json()["answer"]


@pytest.mark.asyncio
async def test_followup_rechecks_role_permission(
    async_client: AsyncClient, chat_db, monkeypatch
):
    monkeypatch.setattr(chat_tools, "get_alerts", lambda **_kwargs: [])
    first = await async_client.post(
        "/api/v1/chat", json={"message": "Có cảnh báo nào không?"},
        headers=_headers("alice", "operator"),
    )
    assert first.status_code == 200
    second = await async_client.post(
        "/api/v1/chat",
        json={"conversation_id": first.json()["conversation_id"], "message": "Còn cảnh báo đó?"},
        headers=_headers("alice", "user"),
    )
    assert second.status_code == 403
    assert len(chat_db.chat_messages.documents) == 2
