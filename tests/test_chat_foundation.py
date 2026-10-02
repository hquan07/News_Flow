from copy import deepcopy
import re
from types import SimpleNamespace

import pytest
from bson import ObjectId
from fastapi import HTTPException
from httpx import AsyncClient

from api.security import create_access_token, permissions_for_role
from api.services import chat_store


class _Cursor:
    def __init__(self, documents):
        self.documents = documents

    def sort(self, field, direction):
        self.documents.sort(key=lambda doc: doc[field], reverse=direction < 0)
        return self

    async def to_list(self, length):
        return deepcopy(self.documents[:length])


class _Collection:
    def __init__(self):
        self.documents = []
        self.indexes = []

    async def create_index(self, fields, **kwargs):
        self.indexes.append((fields, kwargs))

    async def insert_one(self, document):
        stored = deepcopy(document)
        stored["_id"] = ObjectId()
        self.documents.append(stored)
        return SimpleNamespace(inserted_id=stored["_id"])

    async def find_one(self, query):
        found = next((doc for doc in self.documents if self._matches(doc, query)), None)
        return deepcopy(found)

    def find(self, query):
        return _Cursor([deepcopy(doc) for doc in self.documents if self._matches(doc, query)])

    async def update_one(self, query, update):
        found = next((doc for doc in self.documents if self._matches(doc, query)), None)
        if found:
            found.update(deepcopy(update["$set"]))
        return SimpleNamespace(matched_count=int(found is not None))

    async def update_many(self, query, update):
        matched = 0
        for document in self.documents:
            if self._matches(document, query):
                document.update(deepcopy(update["$set"]))
                matched += 1
        return SimpleNamespace(matched_count=matched)

    async def delete_one(self, query):
        found = next((doc for doc in self.documents if self._matches(doc, query)), None)
        if found:
            self.documents.remove(found)
        return SimpleNamespace(deleted_count=int(found is not None))

    async def delete_many(self, query):
        self.documents = [doc for doc in self.documents if not self._matches(doc, query)]

    @staticmethod
    def _matches(document, query):
        return all(
            bool(re.search(value["$regex"], str(document.get(key, "")), re.IGNORECASE))
            if isinstance(value, dict) and "$regex" in value
            else document.get(key) == value
            for key, value in query.items()
        )


@pytest.fixture
def chat_db(monkeypatch):
    database = SimpleNamespace(
        chat_conversations=_Collection(),
        chat_projects=_Collection(),
        chat_messages=_Collection(),
        audit_logs=_Collection(),
    )
    monkeypatch.setattr(chat_store, "get_mongo_db", lambda: database)
    return database


def _headers(subject: str, role: str = "user"):
    token = create_access_token({"sub": subject, "role": role})
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_conversations_are_private_even_from_admin(
    async_client: AsyncClient, chat_db
):
    alice = _headers("alice")
    bob = _headers("bob", "admin")
    created = await async_client.post(
        "/api/v1/chat/conversations", json={"title": "Economy"}, headers=alice
    )
    assert created.status_code == 201
    conversation_id = created.json()["id"]

    own_list = await async_client.get("/api/v1/chat/conversations", headers=alice)
    other_list = await async_client.get("/api/v1/chat/conversations", headers=bob)
    other_detail = await async_client.get(
        f"/api/v1/chat/conversations/{conversation_id}", headers=bob
    )
    other_delete = await async_client.delete(
        f"/api/v1/chat/conversations/{conversation_id}", headers=bob
    )

    assert [item["id"] for item in own_list.json()] == [conversation_id]
    assert other_list.json() == []
    assert other_detail.status_code == 404
    assert other_delete.status_code == 404
    assert (await async_client.get(
        f"/api/v1/chat/conversations/{conversation_id}", headers=alice
    )).status_code == 200


@pytest.mark.asyncio
async def test_message_storage_and_audit_redaction(
    async_client: AsyncClient, chat_db
):
    headers = _headers("alice")
    created = await async_client.post(
        "/api/v1/chat/conversations", json={}, headers=headers
    )
    conversation_id = created.json()["id"]
    content = "My private question about the news"
    message = await chat_store.append_message("alice", conversation_id, "user", content)
    detail = await async_client.get(
        f"/api/v1/chat/conversations/{conversation_id}", headers=headers
    )

    assert len(detail.json()["messages"]) == 1
    assert detail.json()["messages"][0]["id"] == message["id"]
    assert detail.json()["messages"][0]["content"] == content
    assert content not in str(chat_db.audit_logs.documents)
    assert [doc["action"] for doc in chat_db.audit_logs.documents] == [
        "chat.conversation_created", "chat.message_added"
    ]
    assert chat_db.audit_logs.documents[0]["actor_id"] == "alice"

    deleted = await async_client.delete(
        f"/api/v1/chat/conversations/{conversation_id}", headers=headers
    )
    assert deleted.status_code == 204
    assert chat_db.chat_messages.documents == []
    assert chat_db.chat_conversations.documents == []
    assert chat_db.audit_logs.documents[-1]["action"] == "chat.conversation_deleted"


@pytest.mark.asyncio
async def test_chat_rejects_unauthenticated_and_invalid_requests(
    async_client: AsyncClient, chat_db
):
    unauthorized = await async_client.get(
        "/api/v1/chat/conversations", headers={"Authorization": ""}
    )
    assert unauthorized.status_code == 401
    assert (await async_client.post(
        "/api/v1/chat/conversations", json={"title": ""}, headers=_headers("alice")
    )).status_code == 422
    assert (await async_client.get(
        "/api/v1/chat/conversations/not-an-id", headers=_headers("alice")
    )).status_code == 404
    assert (await async_client.get(
        "/api/v1/chat/conversations?limit=101", headers=_headers("alice")
    )).status_code == 422

    with pytest.raises(HTTPException) as denied:
        await chat_store.append_message("bob", str(ObjectId()), "user", "test")
    assert denied.value.status_code == 404


@pytest.mark.asyncio
async def test_chat_indexes_and_role_permission(chat_db):
    await chat_store.ensure_chat_indexes()
    assert len(chat_db.chat_conversations.indexes) == 2
    assert len(chat_db.chat_projects.indexes) == 1
    assert len(chat_db.chat_messages.indexes) == 2
    assert len(chat_db.audit_logs.indexes) == 1
    for role in ("user", "analyst", "operator", "admin"):
        assert "chat.use" in permissions_for_role(role)
