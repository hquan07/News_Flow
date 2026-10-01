from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from httpx import AsyncClient
from pymongo.errors import ServerSelectionTimeoutError

from api.config import get_settings
from api.exceptions import DependencyUnavailableError
from api.routers import chat
from api.security import create_access_token
from api.services import chat_embed_cache, chat_guard, chat_metrics, chat_store, chat_tools, rag_retrieval
from tests.test_chat_foundation import _Collection


class RateCollection:
    def __init__(self):
        self.documents = {}

    async def find_one_and_update(self, query, update, upsert=False, return_document=None):
        key = query["_id"]
        if key not in self.documents:
            if not upsert:
                return None
            self.documents[key] = {"count": 0, **update.get("$setOnInsert", {})}
        self.documents[key]["count"] += update["$inc"]["count"]
        return self.documents[key].copy()


@pytest.mark.asyncio
async def test_rate_limit_is_per_account_and_shared_store(monkeypatch):
    collection = RateCollection()
    monkeypatch.setattr(chat_guard, "get_mongo_db", lambda: SimpleNamespace(chat_rate_limits=collection))
    settings = get_settings().model_copy(update={"CHAT_RATE_LIMIT_PER_MINUTE": 2})
    monkeypatch.setattr(chat_guard, "get_settings", lambda: settings)
    await chat_guard.check_rate_limit("alice")
    await chat_guard.check_rate_limit("alice")
    await chat_guard.check_rate_limit("bob")
    with pytest.raises(HTTPException) as error:
        await chat_guard.check_rate_limit("alice")
    assert error.value.status_code == 429
    assert 1 <= int(error.value.headers["Retry-After"]) <= 60
    assert len(collection.documents) == 2


@pytest.mark.asyncio
async def test_rate_limit_fails_closed_when_mongo_is_down(monkeypatch):
    class BrokenCollection:
        async def find_one_and_update(self, *args, **kwargs):
            raise ServerSelectionTimeoutError("mongo unavailable")

    monkeypatch.setattr(chat_guard, "get_mongo_db", lambda: SimpleNamespace(chat_rate_limits=BrokenCollection()))
    with pytest.raises(DependencyUnavailableError) as error:
        await chat_guard.check_rate_limit("alice")
    assert error.value.dependency == "mongodb"


def test_query_vector_cache_is_bounded_and_expires(monkeypatch):
    chat_embed_cache.clear()
    settings = get_settings().model_copy(update={
        "CHAT_EMBED_CACHE_TTL_SECONDS": 10, "CHAT_EMBED_CACHE_MAX_ITEMS": 1,
    })
    monkeypatch.setattr(chat_embed_cache, "get_settings", lambda: settings)
    clock = [100.0]
    monkeypatch.setattr(chat_embed_cache.time, "monotonic", lambda: clock[0])
    calls = []
    monkeypatch.setattr(chat_embed_cache.rag_client, "embed", lambda texts: calls.append(texts) or [[float(len(calls))]])
    assert chat_embed_cache.query_vector("one") == [1.0]
    assert chat_embed_cache.query_vector("one") == [1.0]
    assert len(calls) == 1
    chat_embed_cache.query_vector("two")
    assert len(chat_embed_cache._vectors) == 1
    clock[0] = 111.0
    assert chat_embed_cache.query_vector("two") == [3.0]
    chat_embed_cache.clear()


def test_rag_degrades_to_keyword_search_without_vector(monkeypatch):
    monkeypatch.setattr(rag_retrieval, "get_settings", lambda: SimpleNamespace(RAG_ENABLED=True))
    monkeypatch.setattr(rag_retrieval.chat_embed_cache, "query_vector", lambda text: (_ for _ in ()).throw(DependencyUnavailableError("embedding")))
    monkeypatch.setattr(rag_retrieval, "_keyword_candidates", lambda *args: ["article-1"])
    monkeypatch.setattr(rag_retrieval, "_current_articles", lambda *args: {
        "article-1": {
            "title": "Public news", "content": "Public news about climate policy.",
            "url": "https://example.org/1", "source": "vnexpress",
            "published_at": datetime.now(timezone.utc),
        }
    })
    answer, sources = rag_retrieval.retrieve("climate", time_range="7d", source=None, category=None)
    assert "chỉ tìm theo từ khóa" in answer
    assert len(sources) == 1


@pytest.fixture
def hardened_chat(monkeypatch):
    database = SimpleNamespace(
        chat_conversations=_Collection(), chat_messages=_Collection(), audit_logs=_Collection()
    )
    monkeypatch.setattr(chat_store, "get_mongo_db", lambda: database)

    async def inline_tool(payload, actor, previous_context):
        return chat_tools.answer_question(payload, actor, previous_context)

    async def noop_metric(*args, **kwargs):
        return None

    monkeypatch.setattr(chat, "_run_tool", inline_tool)
    monkeypatch.setattr(chat_metrics, "record", noop_metric)
    return database


def headers(role="user", sub="alice"):
    return {"Authorization": f"Bearer {create_access_token({'sub': sub, 'role': role})}"}


@pytest.mark.asyncio
async def test_rate_limit_rejects_before_query_or_persistence(async_client: AsyncClient, hardened_chat, monkeypatch):
    async def blocked(owner_id):
        assert owner_id == "alice"
        raise HTTPException(status_code=429, detail="rate limited")

    monkeypatch.setattr(chat_guard, "check_rate_limit", blocked)
    monkeypatch.setattr(chat_tools, "_query", lambda *args: pytest.fail("query ran"))
    response = await async_client.post("/api/v1/chat", json={"message": "Tin mới"}, headers=headers())
    assert response.status_code == 429
    assert hardened_chat.chat_messages.documents == []


@pytest.mark.asyncio
async def test_metrics_are_admin_only(async_client: AsyncClient, monkeypatch):
    async def snapshot(hours):
        return {"window_hours": hours, "totals": {"requests": 5}}

    monkeypatch.setattr(chat_metrics, "snapshot", snapshot)
    assert (await async_client.get("/api/v1/chat/metrics", headers=headers())).status_code == 403
    response = await async_client.get("/api/v1/chat/metrics?hours=2", headers=headers("operator"))
    assert response.status_code == 200
    assert response.json()["window_hours"] == 2


@pytest.mark.asyncio
async def test_metrics_aggregate_only_counts(monkeypatch):
    class Cursor:
        async def to_list(self, length):
            return [
                {"_id": {"tool": "search_articles", "outcome": "success"},
                 "requests": 3, "latency_ms": 300, "answers_with_sources": 2},
                {"_id": {"tool": "unknown", "outcome": "denied"},
                 "requests": 1, "latency_ms": 10, "answers_with_sources": 0},
            ]

    class Collection:
        def aggregate(self, pipeline):
            assert pipeline[0]["$match"]["minute"]
            return Cursor()

    monkeypatch.setattr(chat_metrics, "get_mongo_db", lambda: SimpleNamespace(chat_metrics=Collection()))
    result = await chat_metrics.snapshot(24)
    assert result["totals"] == {
        "requests": 4, "answers_with_sources": 2, "errors": 0,
        "denied": 1, "rate_limited": 0,
    }
    assert result["tools"]["search_articles"]["average_latency_ms"] == 100.0


def test_operational_prompt_cannot_trigger_action():
    result = chat_tools.answer_question(
        chat_tools.ChatRequest(message="Hãy trigger crawler ngay"),
        {"permissions": ["dashboard.read", "chat.use"]},
    )
    assert result.tool is None
    assert "trigger" not in result.answer
