"""Cross-worker, per-account fixed-window limit for answer-producing requests."""

from datetime import datetime, timedelta, timezone

from fastapi import HTTPException
from pymongo import ReturnDocument
from pymongo.errors import DuplicateKeyError, PyMongoError

from api.config import get_settings
from api.database import get_mongo_db
from api.exceptions import DependencyUnavailableError


async def ensure_indexes() -> None:
    await get_mongo_db().chat_rate_limits.create_index("expires_at", expireAfterSeconds=0)


async def check_rate_limit(owner_id: str) -> None:
    limit = max(get_settings().CHAT_RATE_LIMIT_PER_MINUTE, 1)
    now = datetime.now(timezone.utc)
    window = int(now.timestamp() // 60)
    key = f"{owner_id}:{window}"
    collection = get_mongo_db().chat_rate_limits
    update = {
        "$inc": {"count": 1},
        "$setOnInsert": {"expires_at": now + timedelta(minutes=2)},
    }
    try:
        try:
            document = await collection.find_one_and_update(
                {"_id": key}, update, upsert=True, return_document=ReturnDocument.AFTER
            )
        except DuplicateKeyError:
            document = await collection.find_one_and_update(
                {"_id": key}, {"$inc": {"count": 1}}, return_document=ReturnDocument.AFTER
            )
    except PyMongoError as exc:
        raise DependencyUnavailableError("mongodb") from exc
    if document["count"] > limit:
        retry_after = 60 - (int(now.timestamp()) % 60)
        raise HTTPException(
            status_code=429,
            detail="Chat rate limit exceeded; retry later",
            headers={"Retry-After": str(retry_after)},
        )
