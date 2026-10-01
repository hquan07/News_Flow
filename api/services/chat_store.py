"""MongoDB persistence for owner-scoped chatbot conversations.

Only server code may call append_message; clients cannot supply assistant messages.
The audit log records metadata, never the message text.
"""

from datetime import datetime, timezone
from typing import Literal

from bson import ObjectId
from fastapi import HTTPException
from pymongo import ASCENDING, DESCENDING

from api.database import get_mongo_db
from api.middleware import request_id_context


MAX_MESSAGES_PER_CONVERSATION = 200


def _conversation_id(value: str) -> ObjectId:
    if not ObjectId.is_valid(value):
        raise HTTPException(status_code=404, detail="Conversation not found")
    return ObjectId(value)


def _serialize_conversation(document: dict) -> dict:
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
    }


async def ensure_chat_indexes() -> None:
    db = get_mongo_db()
    await db.chat_conversations.create_index(
        [("owner_id", ASCENDING), ("updated_at", DESCENDING)]
    )
    await db.chat_messages.create_index(
        [("conversation_id", ASCENDING), ("created_at", ASCENDING)]
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


async def create_conversation(owner_id: str, title: str) -> dict:
    db = get_mongo_db()
    now = datetime.now(timezone.utc)
    document = {
        "owner_id": owner_id,
        "title": title,
        "created_at": now,
        "updated_at": now,
    }
    result = await db.chat_conversations.insert_one(document)
    document["_id"] = result.inserted_id
    await _audit("chat.conversation_created", owner_id, result.inserted_id)
    return _serialize_conversation(document)


async def list_conversations(owner_id: str, limit: int) -> list[dict]:
    cursor = get_mongo_db().chat_conversations.find({"owner_id": owner_id})
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
