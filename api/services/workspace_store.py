from datetime import datetime, timezone

from bson import ObjectId
from fastapi import HTTPException
from pymongo import ASCENDING, DESCENDING

from api.database import get_mongo_db


def _oid(value: str) -> ObjectId:
    if not ObjectId.is_valid(value):
        raise HTTPException(status_code=404, detail="Workspace not found")
    return ObjectId(value)


def _identity(actor: dict) -> tuple[str, str]:
    return str(actor["sub"]), str(actor.get("email", "")).casefold()


def _serialize(document: dict) -> dict:
    return {**{key: value for key, value in document.items() if key not in {"_id", "name_key"}}, "id": str(document["_id"])}


async def ensure_indexes() -> None:
    db = get_mongo_db()
    await db.team_workspaces.create_index([("owner_id", ASCENDING), ("name_key", ASCENDING)], unique=True)
    await db.workspace_resources.create_index([("workspace_id", ASCENDING), ("updated_at", DESCENDING)])


async def _access(workspace_id: str, actor: dict, *, write: bool = False, owner: bool = False) -> dict:
    document = await get_mongo_db().team_workspaces.find_one({"_id": _oid(workspace_id)})
    if document is None:
        raise HTTPException(status_code=404, detail="Workspace not found")
    actor_id, email = _identity(actor)
    if document["owner_id"] == actor_id:
        return document
    if owner:
        raise HTTPException(status_code=403, detail="Workspace owner permission required")
    member = next((item for item in document.get("members", []) if item["email"].casefold() == email and email), None)
    if member is None or (write and member["role"] != "editor"):
        raise HTTPException(status_code=403, detail="Workspace access denied")
    return document


async def create(actor: dict, name: str) -> dict:
    db = get_mongo_db()
    actor_id, email = _identity(actor)
    now = datetime.now(timezone.utc)
    document = {"owner_id": actor_id, "owner_email": email, "name": name, "name_key": name.casefold(), "members": [], "created_at": now, "updated_at": now}
    if await db.team_workspaces.find_one({"owner_id": actor_id, "name_key": document["name_key"]}):
        raise HTTPException(status_code=409, detail="Workspace name already exists")
    result = await db.team_workspaces.insert_one(document)
    document["_id"] = result.inserted_id
    return _serialize(document)


async def list_accessible(actor: dict) -> list[dict]:
    actor_id, email = _identity(actor)
    documents = await get_mongo_db().team_workspaces.find({}).sort("updated_at", DESCENDING).to_list(length=500)
    return [_serialize(document) for document in documents if document["owner_id"] == actor_id or any(item["email"].casefold() == email and email for item in document.get("members", []))]


async def upsert_member(workspace_id: str, actor: dict, email: str, role: str) -> dict:
    db = get_mongo_db()
    document = await _access(workspace_id, actor, owner=True)
    email = email.casefold()
    if email == document.get("owner_email", "").casefold():
        raise HTTPException(status_code=409, detail="Owner is already a workspace member")
    members = [item for item in document.get("members", []) if item["email"].casefold() != email]
    members.append({"email": email, "role": role})
    now = datetime.now(timezone.utc)
    await db.team_workspaces.update_one({"_id": document["_id"]}, {"$set": {"members": members, "updated_at": now}})
    return _serialize({**document, "members": members, "updated_at": now})


async def remove_member(workspace_id: str, actor: dict, email: str) -> dict:
    db = get_mongo_db()
    document = await _access(workspace_id, actor, owner=True)
    members = [item for item in document.get("members", []) if item["email"].casefold() != email.casefold()]
    now = datetime.now(timezone.utc)
    await db.team_workspaces.update_one({"_id": document["_id"]}, {"$set": {"members": members, "updated_at": now}})
    return _serialize({**document, "members": members, "updated_at": now})


async def create_watchlist(workspace_id: str, actor: dict, payload: dict) -> dict:
    workspace = await _access(workspace_id, actor, write=True)
    now = datetime.now(timezone.utc)
    document = {"workspace_id": workspace["_id"], "resource_type": "watchlist", **payload, "created_by": actor["sub"], "created_at": now, "updated_at": now}
    result = await get_mongo_db().workspace_resources.insert_one(document)
    document["_id"] = result.inserted_id
    serialized = _serialize(document)
    serialized["workspace_id"] = str(document["workspace_id"])
    return serialized


async def list_watchlists(workspace_id: str, actor: dict) -> list[dict]:
    workspace = await _access(workspace_id, actor)
    rows = await get_mongo_db().workspace_resources.find({"workspace_id": workspace["_id"], "resource_type": "watchlist"}).sort("updated_at", DESCENDING).to_list(length=100)
    result = []
    for row in rows:
        item = _serialize(row)
        item["workspace_id"] = str(row["workspace_id"])
        result.append(item)
    return result
