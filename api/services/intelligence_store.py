"""Owner-scoped watchlists, alert rules and scheduled saved searches."""

from datetime import datetime, timedelta, timezone

from bson import ObjectId
from fastapi import HTTPException
from pymongo import ASCENDING, DESCENDING

from api.database import get_mongo_db


COLLECTIONS = {
    "watchlists": "intelligence_watchlists",
    "alert_rules": "intelligence_alert_rules",
    "saved_queries": "intelligence_saved_queries",
}
LIMIT_PER_KIND = 100


def _object_id(value: str, label: str) -> ObjectId:
    if not ObjectId.is_valid(value):
        raise HTTPException(status_code=404, detail=f"{label} not found")
    return ObjectId(value)


def _collection(kind: str):
    return getattr(get_mongo_db(), COLLECTIONS[kind])


def _next_run(schedule: str, now: datetime) -> datetime | None:
    offsets = {"daily": timedelta(days=1), "weekly": timedelta(days=7), "monthly": timedelta(days=30)}
    return now + offsets[schedule] if schedule in offsets else None


def _serialize(document: dict) -> dict:
    return {
        **{key: value for key, value in document.items() if key not in {"_id", "owner_id", "name_key"}},
        "id": str(document["_id"]),
    }


async def ensure_indexes() -> None:
    db = get_mongo_db()
    for collection_name in COLLECTIONS.values():
        collection = getattr(db, collection_name)
        await collection.create_index(
            [("owner_id", ASCENDING), ("name_key", ASCENDING)], unique=True
        )
        await collection.create_index(
            [("owner_id", ASCENDING), ("updated_at", DESCENDING)]
        )
    await db.intelligence_saved_queries.create_index(
        [("enabled", ASCENDING), ("next_run_at", ASCENDING)]
    )


async def create(kind: str, owner_id: str, payload: dict) -> dict:
    collection = _collection(kind)
    existing = await collection.find({"owner_id": owner_id}).to_list(length=LIMIT_PER_KIND)
    if len(existing) >= LIMIT_PER_KIND:
        raise HTTPException(status_code=409, detail="Personal intelligence item limit reached")
    name_key = payload["name"].casefold()
    if await collection.find_one({"owner_id": owner_id, "name_key": name_key}):
        raise HTTPException(status_code=409, detail="Name already exists")
    now = datetime.now(timezone.utc)
    document = {**payload, "owner_id": owner_id, "name_key": name_key, "created_at": now, "updated_at": now}
    if kind == "saved_queries":
        document["next_run_at"] = _next_run(document.get("schedule", "none"), now)
    result = await collection.insert_one(document)
    document["_id"] = result.inserted_id
    return _serialize(document)


async def list_items(kind: str, owner_id: str) -> list[dict]:
    documents = await _collection(kind).find({"owner_id": owner_id}).sort(
        "updated_at", DESCENDING
    ).to_list(length=LIMIT_PER_KIND)
    return [_serialize(document) for document in documents]


async def update(kind: str, owner_id: str, item_id: str, changes: dict) -> dict:
    collection = _collection(kind)
    oid = _object_id(item_id, "Item")
    document = await collection.find_one({"_id": oid, "owner_id": owner_id})
    if document is None:
        raise HTTPException(status_code=404, detail="Item not found")
    changes = {key: value for key, value in changes.items() if value is not None}
    if "name" in changes:
        name_key = changes["name"].casefold()
        duplicate = await collection.find_one({"owner_id": owner_id, "name_key": name_key})
        if duplicate and duplicate["_id"] != oid:
            raise HTTPException(status_code=409, detail="Name already exists")
        changes["name_key"] = name_key
    now = datetime.now(timezone.utc)
    changes["updated_at"] = now
    if kind == "saved_queries" and "schedule" in changes:
        changes["next_run_at"] = _next_run(changes["schedule"], now)
    result = await collection.update_one(
        {"_id": oid, "owner_id": owner_id}, {"$set": changes}
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Item not found")
    return _serialize({**document, **changes})


async def delete(kind: str, owner_id: str, item_id: str) -> None:
    oid = _object_id(item_id, "Item")
    result = await _collection(kind).delete_one({"_id": oid, "owner_id": owner_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Item not found")
