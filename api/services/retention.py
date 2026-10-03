from datetime import datetime, timezone

from fastapi import HTTPException

from api.database import get_mongo_db
from api.services.analytics import _query


DATASETS = {
    "articles": ("newspulse.raw_articles", "publish_time"),
    "social": ("newspulse.social_sentiment_metrics", "publish_time"),
    "keywords": ("newspulse.raw_article_keywords", "loaded_at"),
    "entities": ("newspulse.raw_article_entities", "loaded_at"),
    "sentiment": ("newspulse.raw_article_sentiment", "loaded_at"),
}


async def ensure_indexes() -> None:
    await get_mongo_db().retention_policies.create_index("dataset", unique=True)


def _dataset(name: str) -> tuple[str, str]:
    if name not in DATASETS:
        raise HTTPException(status_code=404, detail="Retention dataset not found")
    return DATASETS[name]


async def list_policies() -> dict:
    rows = await get_mongo_db().retention_policies.find({}).to_list(length=20)
    configured = {row["dataset"]: row for row in rows}
    storage_rows = _query(
        "SELECT table, sum(rows) AS rows, sum(bytes_on_disk) AS bytes_on_disk "
        "FROM system.parts WHERE active AND database = 'newspulse' GROUP BY table"
    )
    storage = {str(row["table"]): row for row in storage_rows}
    return {
        "datasets": [
            {
                "dataset": name,
                "table": table,
                "retention_days": configured.get(name, {}).get("retention_days", 365),
                "enabled": configured.get(name, {}).get("enabled", False),
                "rows": int(storage.get(table.split(".")[-1], {}).get("rows", 0)),
                "bytes_on_disk": int(storage.get(table.split(".")[-1], {}).get("bytes_on_disk", 0)),
            }
            for name, (table, _column) in DATASETS.items()
        ]
    }


async def update_policy(dataset: str, retention_days: int, enabled: bool, actor_id: str) -> dict:
    table, column = _dataset(dataset)
    document = {
        "dataset": dataset, "table": table, "date_column": column,
        "retention_days": retention_days, "enabled": enabled,
        "updated_by": actor_id, "updated_at": datetime.now(timezone.utc),
    }
    await get_mongo_db().retention_policies.update_one(
        {"dataset": dataset}, {"$set": document}, upsert=True
    )
    return document


async def preview(dataset: str) -> dict:
    table, column = _dataset(dataset)
    policy = await get_mongo_db().retention_policies.find_one({"dataset": dataset})
    days = int((policy or {}).get("retention_days", 365))
    rows = _query(
        f"SELECT count() AS rows_to_delete FROM {table} WHERE {column} < now() - toIntervalDay({{days:UInt32}})",
        {"days": days},
    )
    return {"dataset": dataset, "retention_days": days, "rows_to_delete": int(rows[0]["rows_to_delete"]) if rows else 0, "enabled": bool((policy or {}).get("enabled", False))}
