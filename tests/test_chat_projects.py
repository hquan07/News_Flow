"""Projects group owner-owned chats without changing message access or context."""

from types import SimpleNamespace

import pytest
from bson import ObjectId
from httpx import AsyncClient

from api.routers import chat
from api.security import create_access_token
from api.services import chat_guard, chat_metrics, chat_store, chat_tools
from tests.test_chat_foundation import _Collection


@pytest.fixture
def chat_db(monkeypatch):
    database = SimpleNamespace(
        chat_projects=_Collection(),
        chat_conversations=_Collection(),
        chat_messages=_Collection(),
        audit_logs=_Collection(),
    )
    monkeypatch.setattr(chat_store, "get_mongo_db", lambda: database)
    return database


def headers(subject: str, role: str = "user") -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token({'sub': subject, 'role': role})}"}


@pytest.mark.asyncio
async def test_project_delete_ungroups_chats_without_deleting_them(
    async_client: AsyncClient, chat_db
):
    alice = headers("alice")
    created = await async_client.post(
        "/api/v1/chat/projects", json={"title": "  Lãi   suất  "}, headers=alice
    )
    assert created.status_code == 201
    project = created.json()
    assert project["title"] == "Lãi suất"
    project_id = project["id"]
    assert (await async_client.post(
        "/api/v1/chat/projects", json={"title": "lãi suất"}, headers=alice
    )).status_code == 409

    grouped = await async_client.post(
        "/api/v1/chat/conversations",
        json={"title": "Lãi suất ngân hàng", "project_id": project_id},
        headers=alice,
    )
    ungrouped = await async_client.post(
        "/api/v1/chat/conversations", json={"title": "Bài mới"}, headers=alice
    )
    assert grouped.status_code == ungrouped.status_code == 201
    grouped_id = grouped.json()["id"]
    ungrouped_id = ungrouped.json()["id"]
    assert grouped.json()["project_id"] == project_id
    assert ungrouped.json()["project_id"] is None
    filtered = await async_client.get(
        "/api/v1/chat/conversations",
        params={"project_id": project_id, "q": "LÃI", "limit": 100}, headers=alice,
    )
    assert [item["id"] for item in filtered.json()] == [grouped_id]
    assert (await async_client.get(
        "/api/v1/chat/conversations",
        params={"project_id": "unassigned"}, headers=alice,
    )).json()[0]["id"] == ungrouped_id
    assert (await async_client.get(
        "/api/v1/chat/conversations", params={"q": ".*"}, headers=alice,
    )).json() == []
    await chat_store.append_message("alice", grouped_id, "user", "Nội dung riêng")

    renamed = await async_client.patch(
        f"/api/v1/chat/projects/{project_id}",
        json={"title": "Lãi suất 2026"}, headers=alice,
    )
    assert renamed.status_code == 200
    assert renamed.json()["title"] == "Lãi suất 2026"
    moved = await async_client.patch(
        f"/api/v1/chat/conversations/{ungrouped_id}/project",
        json={"project_id": project_id}, headers=alice,
    )
    assert moved.status_code == 200
    assert moved.json()["project_id"] == project_id
    assert (await async_client.patch(
        f"/api/v1/chat/conversations/{ungrouped_id}/project",
        json={"project_id": None}, headers=alice,
    )).json()["project_id"] is None

    deleted = await async_client.delete(f"/api/v1/chat/projects/{project_id}", headers=alice)
    assert deleted.status_code == 204
    assert (await async_client.get("/api/v1/chat/projects", headers=alice)).json() == []
    conversations = (await async_client.get("/api/v1/chat/conversations", headers=alice)).json()
    assert {item["id"] for item in conversations} == {grouped_id, ungrouped_id}
    assert all(item["project_id"] is None for item in conversations)
    detail = (await async_client.get(
        f"/api/v1/chat/conversations/{grouped_id}", headers=alice
    )).json()
    assert detail["messages"][0]["content"] == "Nội dung riêng"
    assert "Nội dung riêng" not in str(chat_db.audit_logs.documents)


@pytest.mark.asyncio
async def test_projects_and_moves_are_owner_scoped_even_for_admin(
    async_client: AsyncClient, chat_db
):
    alice = headers("alice")
    admin = headers("bob", "admin")
    project_id = (await async_client.post(
        "/api/v1/chat/projects", json={"title": "Kinh tế"}, headers=alice
    )).json()["id"]
    alice_chat = (await async_client.post(
        "/api/v1/chat/conversations", json={"title": "Alice"}, headers=alice
    )).json()["id"]
    bob_chat = (await async_client.post(
        "/api/v1/chat/conversations", json={"title": "Bob"}, headers=admin
    )).json()["id"]

    assert (await async_client.get("/api/v1/chat/projects", headers=admin)).json() == []
    assert (await async_client.get(
        "/api/v1/chat/conversations", params={"project_id": project_id}, headers=admin,
    )).status_code == 404
    assert (await async_client.post(
        "/api/v1/chat/projects", json={"title": "Kinh tế"}, headers=admin
    )).status_code == 201
    assert (await async_client.patch(
        f"/api/v1/chat/projects/{project_id}", json={"title": "Đổi tên"}, headers=admin
    )).status_code == 404
    assert (await async_client.delete(
        f"/api/v1/chat/projects/{project_id}", headers=admin
    )).status_code == 404
    assert (await async_client.patch(
        f"/api/v1/chat/conversations/{bob_chat}/project",
        json={"project_id": project_id}, headers=admin,
    )).status_code == 404
    assert (await async_client.patch(
        f"/api/v1/chat/conversations/{alice_chat}/project",
        json={"project_id": None}, headers=admin,
    )).status_code == 404
    assert (await async_client.post(
        "/api/v1/chat/conversations",
        json={"title": "No access", "project_id": project_id}, headers=admin,
    )).status_code == 404
    assert (await async_client.delete(
        "/api/v1/chat/projects/not-an-id", headers=alice
    )).status_code == 404


@pytest.mark.asyncio
async def test_new_chat_starts_in_selected_project_without_cross_chat_context(
    async_client: AsyncClient, chat_db, monkeypatch
):
    async def no_limit(_owner_id):
        return None

    async def no_metric(*_args, **_kwargs):
        return None

    async def fake_tool(_payload, _actor, previous_context):
        assert previous_context is None
        return chat_tools.ToolResult(answer="Chọn chủ đề cụ thể để tìm bài.")

    monkeypatch.setattr(chat_guard, "check_rate_limit", no_limit)
    monkeypatch.setattr(chat_metrics, "record", no_metric)
    monkeypatch.setattr(chat, "_run_tool", fake_tool)
    alice = headers("alice")
    project_id = (await async_client.post(
        "/api/v1/chat/projects", json={"title": "Theo dõi lãi suất"}, headers=alice
    )).json()["id"]
    response = await async_client.post(
        "/api/v1/chat", json={"message": "Xin chào", "project_id": project_id},
        headers=alice,
    )
    assert response.status_code == 200
    conversation_id = response.json()["conversation_id"]
    detail = (await async_client.get(
        f"/api/v1/chat/conversations/{conversation_id}", headers=alice
    )).json()
    assert detail["project_id"] == project_id
    assert [item["role"] for item in detail["messages"]] == ["user", "assistant"]


@pytest.mark.asyncio
async def test_move_rolls_back_if_project_starts_deleting(
    async_client: AsyncClient, chat_db, monkeypatch
):
    alice = headers("alice")
    project_id = (await async_client.post(
        "/api/v1/chat/projects", json={"title": "Tạm thời"}, headers=alice
    )).json()["id"]
    conversation_id = (await async_client.post(
        "/api/v1/chat/conversations", json={"title": "Bài báo"}, headers=alice
    )).json()["id"]
    original_update = chat_db.chat_conversations.update_one

    async def update_during_delete(query, update):
        result = await original_update(query, update)
        if update["$set"].get("project_id") == ObjectId(project_id):
            chat_db.chat_projects.documents[0]["deleting"] = True
        return result

    monkeypatch.setattr(chat_db.chat_conversations, "update_one", update_during_delete)
    moved = await async_client.patch(
        f"/api/v1/chat/conversations/{conversation_id}/project",
        json={"project_id": project_id}, headers=alice,
    )
    assert moved.status_code == 404
    detail = (await async_client.get(
        f"/api/v1/chat/conversations/{conversation_id}", headers=alice
    )).json()
    assert detail["project_id"] is None
