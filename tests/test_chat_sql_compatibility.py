"""Guard against invalid ClickHouse alias/FINAL ordering in chat queries."""

import pytest
from clickhouse_connect.driver.exceptions import DatabaseError
from fastapi import HTTPException

from api.models.chat import ChatRequest
from api.routers import chat
from api.services import chat_tools, rag_retrieval


@pytest.mark.parametrize("message", [
    "Tìm bài viết về AI",
    "Từ khóa nào thịnh hành hôm nay?",
    "Sentiment hôm nay",
    "So sánh nguồn VnExpress và Tuổi Trẻ",
    "Thực thể nào xuất hiện nhiều trong 7 ngày qua?",
    "Thực thể nào liên quan đến VinFast?",
])
def test_chat_queries_place_alias_before_final(monkeypatch, message):
    captured = []

    def fake_query(sql, params):
        captured.append(sql)
        return []

    monkeypatch.setattr(chat_tools, "_query", fake_query)
    chat_tools.answer_question(ChatRequest(message=message), {"permissions": ["dashboard.read"]})
    assert captured
    assert all("FINAL AS" not in sql for sql in captured)


def test_rag_queries_place_alias_before_final(monkeypatch):
    captured = []

    def fake_query(sql, params):
        captured.append(sql)
        return []

    monkeypatch.setattr(rag_retrieval, "_query", fake_query)
    rag_retrieval._keyword_candidates("climate", rag_retrieval.datetime.now(rag_retrieval.timezone.utc), None, None)
    rag_retrieval._current_articles(["article-1"], rag_retrieval.datetime.now(rag_retrieval.timezone.utc), None, None)
    assert len(captured) == 2
    assert all("FINAL AS" not in sql for sql in captured)


@pytest.mark.asyncio
async def test_chat_query_error_is_json_compatible(monkeypatch):
    async def raise_database_error(*args, **kwargs):
        raise DatabaseError("invalid SQL")

    monkeypatch.setattr(chat.asyncio, "to_thread", raise_database_error)
    with pytest.raises(HTTPException) as error:
        await chat._run_tool(ChatRequest(message="Từ khóa nào thịnh hành?"), {"permissions": ["dashboard.read"]}, None)
    assert error.value.status_code == 500
    assert error.value.detail == "Chat data query failed"
