from datetime import datetime, timezone

from bson import ObjectId
from fastapi import HTTPException
from pymongo import ASCENDING, DESCENDING

from api.database import get_mongo_db


def _oid(value: str) -> ObjectId:
    if not ObjectId.is_valid(value):
        raise HTTPException(status_code=404, detail="Crisis room not found")
    return ObjectId(value)


def _serialize(document: dict) -> dict:
    return {**{key: value for key, value in document.items() if key not in {"_id", "owner_id"}}, "id": str(document["_id"])}


async def ensure_indexes() -> None:
    collection = get_mongo_db().crisis_rooms
    await collection.create_index([("owner_id", ASCENDING), ("updated_at", DESCENDING)])
    await collection.create_index([("owner_id", ASCENDING), ("event_id", ASCENDING)], unique=True)


async def create(owner_id: str, payload: dict, snapshot: dict) -> dict:
    collection = get_mongo_db().crisis_rooms
    if await collection.find_one({"owner_id": owner_id, "event_id": payload["event_id"]}):
        raise HTTPException(status_code=409, detail="A room already exists for this event")
    now = datetime.now(timezone.utc)
    document = {**payload, "owner_id": owner_id, "status": "monitoring", "event_snapshot": snapshot, "created_at": now, "updated_at": now}
    result = await collection.insert_one(document)
    document["_id"] = result.inserted_id
    return _serialize(document)


async def list_rooms(owner_id: str) -> list[dict]:
    rows = await get_mongo_db().crisis_rooms.find({"owner_id": owner_id}).sort("updated_at", DESCENDING).to_list(length=100)
    return [_serialize(row) for row in rows]


async def update(owner_id: str, room_id: str, changes: dict) -> dict:
    collection = get_mongo_db().crisis_rooms
    oid = _oid(room_id)
    document = await collection.find_one({"_id": oid, "owner_id": owner_id})
    if document is None:
        raise HTTPException(status_code=404, detail="Crisis room not found")
    changes = {key: value for key, value in changes.items() if value is not None}
    changes["updated_at"] = datetime.now(timezone.utc)
    await collection.update_one({"_id": oid, "owner_id": owner_id}, {"$set": changes})
    return _serialize({**document, **changes})


async def delete(owner_id: str, room_id: str) -> None:
    result = await get_mongo_db().crisis_rooms.delete_one({"_id": _oid(room_id), "owner_id": owner_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Crisis room not found")
