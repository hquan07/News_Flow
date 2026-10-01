from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from api.models.chat import ChatRequest
from api.services import chat_tools, rag_client, rag_indexer, rag_retrieval


def test_chunks_overlap_and_are_deterministic():
    content = " ".join(f"word{i}" for i in range(100))
    first = rag_indexer.chunks(content, size=100, overlap=20)
    assert first == rag_indexer.chunks(content, size=100, overlap=20)
    assert len(first) > 1
    assert first[0][-15:] in content


def test_indexer_skips_unchanged_article(monkeypatch):
    article = {
        "url_hash": "article-1", "url": "https://example.org/1", "title": "News",
        "content": "An article with enough content", "source": "test", "category": "economy",
        "publish_time": datetime.now(timezone.utc),
    }
    state_data = {}

    class State:
        def find_one(self, query):
            return state_data.get(query["_id"])

        def update_one(self, query, update, upsert):
            state_data[query["_id"]] = update["$set"]

    calls = []
    monkeypatch.setattr(rag_indexer.rag_client, "embed", lambda texts: [[0.1, 0.2] for _ in texts])
    monkeypatch.setattr(rag_indexer.rag_client, "ensure_collection", lambda size: calls.append(("ensure", size)))
    monkeypatch.setattr(rag_indexer.rag_client, "delete_article", lambda aid: calls.append(("delete", aid)))
    monkeypatch.setattr(rag_indexer.rag_client, "upsert_points", lambda points: calls.append(("upsert", points)))
    assert rag_indexer.index_article(article, State())
    assert not rag_indexer.index_article(article, State())
    assert [call[0] for call in calls] == ["ensure", "delete", "upsert"]
    assert calls[-1][1][0]["payload"]["article_id"] == "article-1"


def test_qdrant_query_applies_filters(monkeypatch):
    captured = {}

    def fake_call(service, method, url, *, json):
        captured.update(json)
        return SimpleNamespace(json=lambda: {"result": {"points": []}})

    monkeypatch.setattr(rag_client, "_call", fake_call)
    rag_client.query_chunks([0.1], source="vnexpress", category="economy", since=datetime(2026, 1, 1, tzinfo=timezone.utc))
    assert captured["filter"]["must"][1:] == [
        {"key": "source", "match": {"value": "vnexpress"}},
        {"key": "category", "match": {"value": "economy"}},
    ]


def test_rag_denied_before_external_calls(monkeypatch):
    monkeypatch.setattr(chat_tools, "retrieve", lambda *args, **kwargs: pytest.fail("RAG was called"))
    with pytest.raises(HTTPException) as error:
        chat_tools.answer_question(ChatRequest(message="Tóm tắt nội dung bài viết"), {"permissions": []})
    assert error.value.status_code == 403


def test_retrieval_revalidates_and_never_quotes_stale_payload(monkeypatch):
    monkeypatch.setattr(rag_retrieval, "get_settings", lambda: SimpleNamespace(RAG_ENABLED=True))
    monkeypatch.setattr(rag_retrieval.rag_client, "embed", lambda texts: [[0.1]])
    monkeypatch.setattr(rag_retrieval.rag_client, "query_chunks", lambda *args, **kwargs: [
        {"payload": {"article_id": "valid", "text": "old secret text"}},
        {"payload": {"article_id": "removed", "text": "removed article"}},
    ])
    monkeypatch.setattr(rag_retrieval, "_keyword_candidates", lambda *args: [])
    article = {
        "article_id": "valid", "title": "Current article", "content": "Current public article text about climate.",
        "url": "https://example.org/current", "source": "vnexpress", "published_at": datetime.now(timezone.utc),
    }
    monkeypatch.setattr(rag_retrieval, "_query", lambda sql, params: [article])
    answer, sources = rag_retrieval.retrieve("climate", time_range="7d", source="vnexpress", category=None)
    assert len(sources) == 1
    assert sources[0]["article_id"] == "valid"
    assert "Current public article" in answer
    assert "old secret" not in answer
    assert "removed article" not in answer


def test_rag_disabled_is_explicit(monkeypatch):
    monkeypatch.setattr(rag_retrieval, "get_settings", lambda: SimpleNamespace(RAG_ENABLED=False))
    answer, sources = rag_retrieval.retrieve("anything", time_range="7d", source=None, category=None)
    assert "chưa được bật" in answer
    assert sources == []


def test_keyword_only_result_keeps_clickhouse_filters(monkeypatch):
    monkeypatch.setattr(rag_retrieval, "get_settings", lambda: SimpleNamespace(RAG_ENABLED=True))
    monkeypatch.setattr(rag_retrieval.rag_client, "embed", lambda texts: [[0.1]])
    monkeypatch.setattr(rag_retrieval.rag_client, "query_chunks", lambda *args, **kwargs: [])
    queries = []

    def fake_query(sql, params):
        queries.append((sql, params))
        if sql.startswith("SELECT a.url_hash AS article_id FROM"):
            return [{"article_id": "keyword-match"}]
        return [{
            "article_id": "keyword-match", "title": "Climate bulletin",
            "content": "Climate policy changed this week.",
            "url": "https://example.org/climate", "source": "vnexpress",
            "published_at": datetime.now(timezone.utc),
        }]

    monkeypatch.setattr(rag_retrieval, "_query", fake_query)
    answer, sources = rag_retrieval.retrieve(
        "climate", time_range="today", source="vnexpress", category="world"
    )
    assert len(sources) == 1
    assert "Climate policy" in answer
    assert len(queries) == 2
    for sql, params in queries:
        assert "a.source = {source:String}" in sql
        assert "a.category = {category:String}" in sql
        assert "a.publish_time >= {since:DateTime}" in sql
        assert params["source"] == "vnexpress"
        assert params["category"] == "world"
