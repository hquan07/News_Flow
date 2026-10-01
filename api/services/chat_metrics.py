"""Privacy-preserving chatbot counters; no prompts or answer text are stored."""

from datetime import datetime, timedelta, timezone

from api.database import get_mongo_db


async def ensure_indexes() -> None:
    await get_mongo_db().chat_metrics.create_index("expires_at", expireAfterSeconds=0)


async def record(tool: str, outcome: str, duration_seconds: float, source_count: int = 0) -> None:
    minute = datetime.now(timezone.utc).replace(second=0, microsecond=0)
    bucket = f"{int(minute.timestamp())}:{tool}:{outcome}"
    await get_mongo_db().chat_metrics.update_one(
        {"_id": bucket},
        {
            "$inc": {
                "requests": 1,
                "latency_ms": max(duration_seconds, 0) * 1000,
                "answers_with_sources": int(source_count > 0),
            },
            "$setOnInsert": {
                "minute": minute,
                "tool": tool,
                "outcome": outcome,
                "expires_at": minute + timedelta(days=7),
            },
        },
        upsert=True,
    )


async def snapshot(hours: int = 24) -> dict:
    since = datetime.now(timezone.utc) - timedelta(hours=hours)
    cursor = get_mongo_db().chat_metrics.aggregate([
        {"$match": {"minute": {"$gte": since}}},
        {"$group": {
            "_id": {"tool": "$tool", "outcome": "$outcome"},
            "requests": {"$sum": "$requests"},
            "latency_ms": {"$sum": "$latency_ms"},
            "answers_with_sources": {"$sum": "$answers_with_sources"},
        }},
    ])
    rows = await cursor.to_list(length=1000)
    totals = {"requests": 0, "answers_with_sources": 0, "errors": 0, "denied": 0, "rate_limited": 0}
    tools: dict[str, dict] = {}
    for row in rows:
        count = int(row.get("requests", 0))
        outcome = row.get("_id", {}).get("outcome", "error")
        tool = row.get("_id", {}).get("tool", "unknown")
        metric = tools.setdefault(tool, {"requests": 0, "latency_ms": 0.0, "answers_with_sources": 0})
        metric["requests"] += count
        metric["latency_ms"] += float(row.get("latency_ms", 0))
        metric["answers_with_sources"] += int(row.get("answers_with_sources", 0))
        totals["requests"] += count
        totals["answers_with_sources"] += int(row.get("answers_with_sources", 0))
        if outcome in ("errors", "denied", "rate_limited"):
            totals[outcome] += count
    for metric in tools.values():
        metric["average_latency_ms"] = round(metric.pop("latency_ms") / metric["requests"], 2)
    return {"window_hours": hours, "totals": totals, "tools": tools}
