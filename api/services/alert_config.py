"""Shared alert threshold configuration stored in MongoDB."""

from datetime import datetime, timezone

from api.database import get_mongo_db


DEFAULT_ALERT_THRESHOLDS = {
    "crisis_negative_pct": 30.0,
    "crisis_min_posts": 10,
    "viral_interactions": 50,
}


async def get_alert_thresholds() -> dict:
    document = await get_mongo_db().alert_config.find_one(
        {"_id": "thresholds"},
        {"_id": 0, "updated_at": 0, "updated_by": 0},
    )
    return {**DEFAULT_ALERT_THRESHOLDS, **(document or {})}


async def update_alert_thresholds(values: dict, user_id: str) -> dict:
    thresholds = {**DEFAULT_ALERT_THRESHOLDS, **values}
    await get_mongo_db().alert_config.update_one(
        {"_id": "thresholds"},
        {
            "$set": {
                **thresholds,
                "updated_at": datetime.now(timezone.utc),
                "updated_by": user_id,
            }
        },
        upsert=True,
    )
    return thresholds
