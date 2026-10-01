from datetime import datetime, timezone
from typing import Literal

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, model_validator

from api.database import get_mongo_db
from api.security import require_permission


router = APIRouter(prefix="/admin", tags=["User Management"])


class UserAccessUpdate(BaseModel):
    role: Literal["user", "analyst", "operator", "admin"] | None = None
    is_active: bool | None = None

    @model_validator(mode="after")
    def require_change(self):
        if self.role is None and self.is_active is None:
            raise ValueError("At least one access field is required")
        return self


def _object_id(value: str) -> ObjectId:
    if not ObjectId.is_valid(value):
        raise HTTPException(status_code=404, detail="User not found")
    return ObjectId(value)


def _serialize_user(document: dict) -> dict:
    return {
        "id": str(document["_id"]),
        "email": document.get("email", ""),
        "full_name": document.get("full_name", ""),
        "avatar_data_url": document.get("avatar_data_url"),
        "role": document.get("role", "user"),
        "is_active": document.get("is_active", True),
        "created_at": document.get("created_at"),
    }


@router.get("/users")
async def list_users(
    limit: int = Query(default=100, ge=1, le=500),
    _actor: dict = Depends(require_permission("users.manage")),
):
    db = get_mongo_db()
    documents = await db.users.find(
        {},
        {"password": 0},
    ).sort("created_at", -1).to_list(length=limit)
    return {"users": [_serialize_user(document) for document in documents]}


@router.patch("/users/{user_id}")
async def update_user_access(
    user_id: str,
    update: UserAccessUpdate,
    actor: dict = Depends(require_permission("users.manage")),
):
    if actor["sub"] == user_id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="You cannot change your own role or active status",
        )

    db = get_mongo_db()
    object_id = _object_id(user_id)
    target = await db.users.find_one({"_id": object_id}, {"password": 0})
    if target is None:
        raise HTTPException(status_code=404, detail="User not found")

    changes = update.model_dump(exclude_none=True)
    changes["updated_at"] = datetime.now(timezone.utc)
    await db.users.update_one({"_id": object_id}, {"$set": changes})

    await db.audit_logs.insert_one({
        "action": "user.access_updated",
        "actor_id": actor["sub"],
        "actor_email": actor.get("email", ""),
        "target_id": user_id,
        "target_email": target.get("email", ""),
        "changes": update.model_dump(exclude_none=True),
        "created_at": datetime.now(timezone.utc),
    })

    updated = await db.users.find_one({"_id": object_id}, {"password": 0})
    return _serialize_user(updated)


@router.get("/audit-logs")
async def list_audit_logs(
    limit: int = Query(default=50, ge=1, le=200),
    _actor: dict = Depends(require_permission("audit.read")),
):
    db = get_mongo_db()
    documents = await db.audit_logs.find({}).sort("created_at", -1).to_list(length=limit)
    return {
        "logs": [
            {
                "id": str(document["_id"]),
                "action": document.get("action", ""),
                "actor_email": document.get("actor_email", ""),
                "target_email": document.get("target_email", ""),
                "changes": document.get("changes", {}),
                "created_at": document.get("created_at"),
            }
            for document in documents
        ]
    }
