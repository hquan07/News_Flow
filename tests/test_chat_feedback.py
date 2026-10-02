"""Per-answer feedback stays owner-scoped and never duplicates chat text."""

from types import SimpleNamespace

import pytest

from api.routers import chat
from api.security import create_access_token
from api.services import chat_guard, chat_metrics, chat_store, chat_tools
from tests.test_chat_foundation import _Collection


def headers(subject="alice", role="user"):
    token = create_access_token({"sub": subject, "role": role})
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def chat_db(monkeypatch):
    db = SimpleNamespace(
        chat_conversations=_Collection(), chat_messages=_Collection(), audit_logs=_Collection(),
    )
    monkeypatch.setattr(chat_store, "get_mongo_db", lambda: db)

    async def inline_tool(payload, actor, context):
        return chat_tools.answer_question(payload, actor, context)

    async def noop(*_args, **_kwargs):
        return None

    monkeypatch.setattr(chat, "_run_tool", inline_tool)
    monkeypatch.setattr(chat_guard, "check_rate_limit", noop)
    monkeypatch.setattr(chat_metrics, "record", noop)
    return db


@pytest.mark.asyncio
async def test_feedback_saved_on_own_assistant_message_and_can_change(async_client, chat_db):
    answer = await async_client.post(
        "/api/v1/chat", json={"message": "Tổng số bài báo"}, headers=headers(),
    )
    assert answer.status_code == 200
    conversation_id = answer.json()["conversation_id"]
    message_id = answer.json()["message_id"]
    assert message_id
    url = f"/api/v1/chat/conversations/{conversation_id}/messages/{message_id}/feedback"
    first = await async_client.put(url, json={"reason": "wrong_source"}, headers=headers())
    assert first.status_code == 200
    assert first.json()["reason"] == "wrong_source"
    second = await async_client.put(url, json={"reason": "helpful"}, headers=headers())
    assert second.status_code == 200
    detail = await async_client.get(f"/api/v1/chat/conversations/{conversation_id}", headers=headers())
    assert detail.json()["messages"][-1]["feedback"]["reason"] == "helpful"
    assert "content" not in str(chat_db.chat_messages.documents[-1]["feedback"])
    assert "Tổng số bài báo" not in str(chat_db.audit_logs.documents)


@pytest.mark.asyncio
async def test_feedback_rejects_other_owner_user_message_and_invalid_reason(async_client, chat_db):
    answer = await async_client.post(
        "/api/v1/chat", json={"message": "Tổng số bài báo"}, headers=headers(),
    )
    conversation_id = answer.json()["conversation_id"]
    message_id = answer.json()["message_id"]
    url = f"/api/v1/chat/conversations/{conversation_id}/messages/{message_id}/feedback"
    assert (await async_client.put(url, json={"reason": "wrong_number"}, headers=headers("bob", "admin"))).status_code == 404
    assert (await async_client.put(url, json={"reason": "other"}, headers=headers())).status_code == 422
    user_id = str(chat_db.chat_messages.documents[0]["_id"])
    user_url = f"/api/v1/chat/conversations/{conversation_id}/messages/{user_id}/feedback"
    assert (await async_client.put(user_url, json={"reason": "helpful"}, headers=headers())).status_code == 404


@pytest.mark.asyncio
async def test_feedback_summary_requires_system_permission(async_client, chat_db, monkeypatch):
    async def summary(days):
        return {"window_days": days, "counts": []}

    monkeypatch.setattr(chat_store, "feedback_summary", summary)
    assert (await async_client.get("/api/v1/chat/feedback/summary", headers=headers())).status_code == 403
    response = await async_client.get("/api/v1/chat/feedback/summary?days=14", headers=headers("admin", "admin"))
    assert response.status_code == 200
    assert response.json()["window_days"] == 14
