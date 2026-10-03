from datetime import datetime, timezone

from fastapi import HTTPException

from api.database import get_mongo_db


async def ensure_indexes() -> None:
    await get_mongo_db().source_settings.create_index("spider_name", unique=True)


async def settings_map() -> dict[str, dict]:
    rows = await get_mongo_db().source_settings.find({}).to_list(length=200)
    return {row["spider_name"]: row for row in rows}


async def update(spider_name: str, changes: dict, actor_id: str) -> dict:
    if not changes:
        raise HTTPException(status_code=422, detail="At least one source setting is required")
    document = {
        **changes, "spider_name": spider_name, "updated_by": actor_id,
        "updated_at": datetime.now(timezone.utc),
    }
    await get_mongo_db().source_settings.update_one(
        {"spider_name": spider_name}, {"$set": document}, upsert=True
    )
    return document
