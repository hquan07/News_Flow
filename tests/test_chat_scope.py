"""Scope transparency, clarification, and evaluated routing contracts."""

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from api.routers import chat
from api.security import create_access_token
from api.services import chat_guard, chat_metrics, chat_store, chat_tools
from scripts.evaluate_chatbot import evaluate_offline
from tests.test_chat_foundation import _Collection


@pytest.fixture
def chat_db(monkeypatch):
    database = SimpleNamespace(
        chat_conversations=_Collection(),
        chat_messages=_Collection(),
        audit_logs=_Collection(),
    )
    monkeypatch.setattr(chat_store, "get_mongo_db", lambda: database)

    async def inline_tool(payload, actor, previous_context):
        return chat_tools.answer_question(payload, actor, previous_context)

    async def noop(*_args, **_kwargs):
        return None

    monkeypatch.setattr(chat, "_run_tool", inline_tool)
    monkeypatch.setattr(chat_guard, "check_rate_limit", noop)
    monkeypatch.setattr(chat_metrics, "record", noop)
    return database


def headers(role="user"):
    token = create_access_token({"sub": "scope-user", "role": role})
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_ambiguous_count_asks_before_query_and_followup_resolves(async_client, chat_db, monkeypatch):
    calls = []

    def fake_query(sql, params):
        calls.append((sql, params))
        return [{"article_count": 7}]

    monkeypatch.setattr(chat_tools, "_query", fake_query)
    first = await async_client.post("/api/v1/chat", json={"message": "Tổng số bài báo"}, headers=headers())
    assert first.status_code == 200
    assert first.json()["tool"] == "clarify_scope"
    assert first.json()["context"]["clarification"] is True
    assert first.json()["queried_at"] is None
    assert calls == []

    second = await async_client.post(
        "/api/v1/chat",
        json={"conversation_id": first.json()["conversation_id"], "message": "VnExpress trong 7 ngày qua"},
        headers=headers(),
    )
    assert second.status_code == 200
    assert second.json()["tool"] == "count_articles"
    assert second.json()["context"]["time_range"] == "7d"
    assert second.json()["context"]["source"] == "vnexpress"
    assert calls[0][1] == {"source": "vnexpress"}
    assert "7 DAY" in calls[0][0]
    detail = await async_client.get(
        f"/api/v1/chat/conversations/{first.json()['conversation_id']}", headers=headers()
    )
    assert detail.json()["messages"][-1]["context"]["source"] == "vnexpress"


@pytest.mark.asyncio
async def test_compare_clarification_accepts_two_sources_as_reply(async_client, chat_db, monkeypatch):
    captured = {}

    def fake_query(sql, params):
        captured.update(params=params)
        return []

    monkeypatch.setattr(chat_tools, "_query", fake_query)
    first = await async_client.post("/api/v1/chat", json={"message": "So sánh nguồn"}, headers=headers())
    assert first.json()["tool"] == "clarify_scope"
    second = await async_client.post(
        "/api/v1/chat",
        json={"conversation_id": first.json()["conversation_id"], "message": "VnExpress và Tuổi Trẻ"},
        headers=headers(),
    )
    assert second.json()["tool"] == "compare_sources"
    assert second.json()["context"]["compare_sources"] == ["vnexpress", "tuoitre"]
    assert captured["params"]["source_names"] == ["vnexpress", "tuoitre"]


@pytest.mark.asyncio
async def test_conflicting_filters_do_not_query(async_client, chat_db, monkeypatch):
    monkeypatch.setattr(chat_tools, "_query", lambda *_args: pytest.fail("queried with conflicting scope"))
    response = await async_client.post(
        "/api/v1/chat",
        json={"message": "Tin mới hôm nay", "time_range": "30d"},
        headers=headers(),
    )
    assert response.status_code == 200
    assert response.json()["tool"] == "clarify_scope"
    assert "thời gian" in response.json()["answer"]


@pytest.mark.asyncio
async def test_resolved_scope_matches_count_query(async_client, chat_db, monkeypatch):
    captured = {}

    def fake_query(sql, params):
        captured.update(sql=sql, params=params)
        return [{"article_count": 3}]

    monkeypatch.setattr(chat_tools, "_query", fake_query)
    response = await async_client.post(
        "/api/v1/chat",
        json={"message": "Có bao nhiêu bài báo về AI từ Tuổi Trẻ?", "time_range": "7d"},
        headers=headers(),
    )
    assert response.status_code == 200
    context = response.json()["context"]
    assert context["time_range"] == "7d"
    assert context["source"] == "tuoitre"
    assert context["query"] == "AI"
    assert captured["params"] == {"source": "tuoitre", "title_query": "%AI%"}


def test_offline_eval_checks_expectations_not_just_router_output():
    dataset = json.loads((Path(__file__).parents[1] / "eval/chatbot_cases.json").read_text(encoding="utf-8"))
    assert len(dataset) >= 30
    assert len({case["id"] for case in dataset}) == len(dataset)
    assert evaluate_offline(dataset) == []
    wrong = [{**dataset[0], "expected_time_range": "30d"}]
    assert evaluate_offline(wrong)
