from datetime import datetime, timezone

from api.database import get_mongo_db


async def get_alert_states(user_id: str, alert_ids: list[str]) -> list[dict]:
    if not alert_ids:
        return []
    db = get_mongo_db()
    cursor = db.alert_states.find(
        {"user_id": user_id, "alert_id": {"$in": alert_ids}},
        {"_id": 0},
    )
    return await cursor.to_list(length=min(len(alert_ids), 100))


async def update_alert_state(
    user_id: str,
    alert_id: str,
    pinned: bool | None = None,
    acknowledged: bool | None = None,
) -> dict:
    db = get_mongo_db()
    now = datetime.now(timezone.utc)
    state_id = f"{user_id}:{alert_id}"
    updates = {"updated_at": now}
    if pinned is not None:
        updates["pinned"] = pinned
    if acknowledged is not None:
        updates["acknowledged"] = acknowledged

    await db.alert_states.update_one(
        {"_id": state_id},
        {
            "$set": updates,
            "$setOnInsert": {
                "user_id": user_id,
                "alert_id": alert_id,
                "created_at": now,
            },
        },
        upsert=True,
    )
    document = await db.alert_states.find_one({"_id": state_id}, {"_id": 0})
    return document
