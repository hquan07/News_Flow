"""MongoDB persistence for owner-scoped chatbot conversations.

Only server code may call append_message; clients cannot supply assistant messages.
The audit log records metadata, never the message text.
"""

import re
from datetime import datetime, timezone
from typing import Literal

from bson import ObjectId
from fastapi import HTTPException
from pymongo import ASCENDING, DESCENDING
from pymongo.errors import DuplicateKeyError

from api.database import get_mongo_db
from api.middleware import request_id_context


MAX_MESSAGES_PER_CONVERSATION = 200
MAX_PROJECTS_PER_OWNER = 100


def _conversation_id(value: str) -> ObjectId:
    if not ObjectId.is_valid(value):
        raise HTTPException(status_code=404, detail="Conversation not found")
    return ObjectId(value)


def _project_id(value: str) -> ObjectId:
    if not ObjectId.is_valid(value):
        raise HTTPException(status_code=404, detail="Project not found")
    return ObjectId(value)


def _serialize_conversation(document: dict) -> dict:
    return {
        "id": str(document["_id"]),
        "title": document["title"],
        "project_id": str(document["project_id"]) if document.get("project_id") else None,
        "created_at": document["created_at"],
        "updated_at": document["updated_at"],
    }


def _serialize_project(document: dict) -> dict:
    return {
        "id": str(document["_id"]),
        "title": document["title"],
        "created_at": document["created_at"],
        "updated_at": document["updated_at"],
    }


def _serialize_message(document: dict) -> dict:
    return {
        "id": str(document["_id"]),
        "conversation_id": str(document["conversation_id"]),
        "role": document["role"],
        "content": document["content"],
        "created_at": document["created_at"],
        "sources": document.get("sources", []),
        "tool": document.get("tool"),
        "queried_at": document.get("queried_at"),
        "chart": document.get("chart"),
        "context": document.get("context"),
    }


async def ensure_chat_indexes() -> None:
    db = get_mongo_db()
    await db.chat_conversations.create_index(
        [("owner_id", ASCENDING), ("updated_at", DESCENDING)]
    )
    await db.chat_messages.create_index(
        [("conversation_id", ASCENDING), ("created_at", ASCENDING)]
    )
    await db.chat_conversations.create_index(
        [("owner_id", ASCENDING), ("project_id", ASCENDING), ("updated_at", DESCENDING)]
    )
    await db.chat_projects.create_index(
        [("owner_id", ASCENDING), ("title_key", ASCENDING)], unique=True
    )
    await db.audit_logs.create_index(
        [("actor_id", ASCENDING), ("created_at", DESCENDING)]
    )


async def _audit(action: str, owner_id: str, conversation_id: ObjectId) -> None:
    await get_mongo_db().audit_logs.insert_one({
        "action": action,
        "actor_id": owner_id,
        "conversation_id": str(conversation_id),
        "request_id": request_id_context.get(),
        "created_at": datetime.now(timezone.utc),
    })


async def _audit_project(action: str, owner_id: str, project_id: ObjectId) -> None:
    await get_mongo_db().audit_logs.insert_one({
        "action": action,
        "actor_id": owner_id,
        "project_id": str(project_id),
        "request_id": request_id_context.get(),
        "created_at": datetime.now(timezone.utc),
    })


async def _owned_project(owner_id: str, project_id: str) -> dict:
    document = await get_mongo_db().chat_projects.find_one({
        "_id": _project_id(project_id), "owner_id": owner_id,
    })
    if document is None or document.get("deleting"):
        raise HTTPException(status_code=404, detail="Project not found")
    return document


async def create_project(owner_id: str, title: str) -> dict:
    db = get_mongo_db()
    title_key = title.casefold()
    if await db.chat_projects.find_one({"owner_id": owner_id, "title_key": title_key}):
        raise HTTPException(status_code=409, detail="Project name already exists")
    existing = await db.chat_projects.find({"owner_id": owner_id}).to_list(
        length=MAX_PROJECTS_PER_OWNER
    )
    if len(existing) >= MAX_PROJECTS_PER_OWNER:
        raise HTTPException(status_code=409, detail="Project limit reached")
    now = datetime.now(timezone.utc)
    document = {
        "owner_id": owner_id, "title": title, "title_key": title_key,
        "created_at": now, "updated_at": now,
    }
    try:
        result = await db.chat_projects.insert_one(document)
    except DuplicateKeyError as exc:
        raise HTTPException(status_code=409, detail="Project name already exists") from exc
    document["_id"] = result.inserted_id
    await _audit_project("chat.project_created", owner_id, result.inserted_id)
    return _serialize_project(document)


async def list_projects(owner_id: str) -> list[dict]:
    cursor = get_mongo_db().chat_projects.find({"owner_id": owner_id})
    documents = await cursor.sort("created_at", ASCENDING).to_list(
        length=MAX_PROJECTS_PER_OWNER
    )
    return [_serialize_project(document) for document in documents]


async def rename_project(owner_id: str, project_id: str, title: str) -> dict:
    db = get_mongo_db()
    document = await _owned_project(owner_id, project_id)
    title_key = title.casefold()
    duplicate = await db.chat_projects.find_one({
        "owner_id": owner_id, "title_key": title_key,
    })
    if duplicate and duplicate["_id"] != document["_id"]:
        raise HTTPException(status_code=409, detail="Project name already exists")
    now = datetime.now(timezone.utc)
    try:
        updated = await db.chat_projects.update_one(
            {"_id": document["_id"], "owner_id": owner_id},
            {"$set": {"title": title, "title_key": title_key, "updated_at": now}},
        )
    except DuplicateKeyError as exc:
        raise HTTPException(status_code=409, detail="Project name already exists") from exc
    if updated.matched_count == 0:
        raise HTTPException(status_code=404, detail="Project not found")
    await _audit_project("chat.project_renamed", owner_id, document["_id"])
    return _serialize_project({**document, "title": title, "updated_at": now})


async def delete_project(owner_id: str, project_id: str) -> None:
    db = get_mongo_db()
    document = await _owned_project(owner_id, project_id)
    marked = await db.chat_projects.update_one(
        {"_id": document["_id"], "owner_id": owner_id},
        {"$set": {"deleting": True}},
    )
    if marked.matched_count == 0:
        raise HTTPException(status_code=404, detail="Project not found")
    try:
        # Deleting a group never deletes a conversation or any message.
        await db.chat_conversations.update_many(
            {"owner_id": owner_id, "project_id": document["_id"]},
            {"$set": {"project_id": None}},
        )
        deleted = await db.chat_projects.delete_one({
            "_id": document["_id"], "owner_id": owner_id,
        })
        if deleted.deleted_count == 0:
            raise HTTPException(status_code=404, detail="Project not found")
    except Exception:
        await db.chat_projects.update_one(
            {"_id": document["_id"], "owner_id": owner_id},
            {"$set": {"deleting": False}},
        )
        raise
    await _audit_project("chat.project_deleted", owner_id, document["_id"])


async def move_conversation(owner_id: str, conversation_id: str, project_id: str | None) -> dict:
    db = get_mongo_db()
    target_id = (await _owned_project(owner_id, project_id))["_id"] if project_id else None
    oid = _conversation_id(conversation_id)
    updated = await db.chat_conversations.update_one(
        {"_id": oid, "owner_id": owner_id},
        {"$set": {"project_id": target_id}},
    )
    if updated.matched_count == 0:
        raise HTTPException(status_code=404, detail="Conversation not found")
    if target_id:
        try:
            await _owned_project(owner_id, project_id)
        except HTTPException:
            await db.chat_conversations.update_one(
                {"_id": oid, "owner_id": owner_id, "project_id": target_id},
                {"$set": {"project_id": None}},
            )
            raise
    document = await db.chat_conversations.find_one({"_id": oid, "owner_id": owner_id})
    if document is None:
        raise HTTPException(status_code=404, detail="Conversation not found")
    await _audit("chat.conversation_moved", owner_id, oid)
    return _serialize_conversation(document)


async def create_conversation(owner_id: str, title: str, project_id: str | None = None) -> dict:
    db = get_mongo_db()
    project_oid = (await _owned_project(owner_id, project_id))["_id"] if project_id else None
    now = datetime.now(timezone.utc)
    document = {
        "owner_id": owner_id,
        "title": title,
        "project_id": project_oid,
        "created_at": now,
        "updated_at": now,
    }
    result = await db.chat_conversations.insert_one(document)
    document["_id"] = result.inserted_id
    if project_oid:
        try:
            await _owned_project(owner_id, project_id)
        except HTTPException:
            await db.chat_conversations.delete_one({"_id": result.inserted_id, "owner_id": owner_id})
            raise
    await _audit("chat.conversation_created", owner_id, result.inserted_id)
    return _serialize_conversation(document)


async def list_conversations(
    owner_id: str, limit: int, project_id: str | None = None, q: str | None = None
) -> list[dict]:
    query: dict = {"owner_id": owner_id}
    if project_id == "unassigned":
        query["project_id"] = None
    elif project_id:
        query["project_id"] = (await _owned_project(owner_id, project_id))["_id"]
    if q and q.strip():
        query["title"] = {"$regex": re.escape(q.strip()), "$options": "i"}
    cursor = get_mongo_db().chat_conversations.find(query)
    documents = await cursor.sort("updated_at", DESCENDING).to_list(length=limit)
    return [_serialize_conversation(document) for document in documents]


async def get_conversation(owner_id: str, conversation_id: str) -> dict:
    db = get_mongo_db()
    oid = _conversation_id(conversation_id)
    document = await db.chat_conversations.find_one({"_id": oid, "owner_id": owner_id})
    if document is None:
        raise HTTPException(status_code=404, detail="Conversation not found")
    messages = await db.chat_messages.find({
        "conversation_id": oid,
        "owner_id": owner_id,
    }).sort("created_at", DESCENDING).to_list(length=MAX_MESSAGES_PER_CONVERSATION)
    return {
        **_serialize_conversation(document),
        "messages": [_serialize_message(message) for message in reversed(messages)],
    }


async def append_message(
    owner_id: str,
    conversation_id: str,
    role: Literal["user", "assistant"],
    content: str,
    *,
    sources: list[dict] | None = None,
    tool: str | None = None,
    queried_at: datetime | None = None,
    chart: dict | None = None,
    context: dict | None = None,
) -> dict:
    if role not in ("user", "assistant") or not content.strip() or len(content) > 16000:
        raise ValueError("Invalid chat message")
    db = get_mongo_db()
    oid = _conversation_id(conversation_id)
    now = datetime.now(timezone.utc)
    updated = await db.chat_conversations.update_one(
        {"_id": oid, "owner_id": owner_id},
        {"$set": {"updated_at": now}},
    )
    if updated.matched_count == 0:
        raise HTTPException(status_code=404, detail="Conversation not found")
    document = {
        "conversation_id": oid,
        "owner_id": owner_id,
        "role": role,
        "content": content,
        "created_at": now,
        "sources": sources or [],
        "tool": tool,
        "queried_at": queried_at,
        "chart": chart,
        "context": context,
    }
    result = await db.chat_messages.insert_one(document)
    document["_id"] = result.inserted_id
    # A concurrent delete may remove the conversation between the update and insert.
    if await db.chat_conversations.find_one({"_id": oid, "owner_id": owner_id}) is None:
        await db.chat_messages.delete_one({"_id": result.inserted_id, "owner_id": owner_id})
        raise HTTPException(status_code=404, detail="Conversation not found")
    await _audit("chat.message_added", owner_id, oid)
    return _serialize_message(document)


async def delete_conversation(owner_id: str, conversation_id: str) -> None:
    db = get_mongo_db()
    oid = _conversation_id(conversation_id)
    result = await db.chat_conversations.delete_one({"_id": oid, "owner_id": owner_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Conversation not found")
    await db.chat_messages.delete_many({"conversation_id": oid, "owner_id": owner_id})
    await _audit("chat.conversation_deleted", owner_id, oid)
