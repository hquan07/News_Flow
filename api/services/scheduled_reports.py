from datetime import datetime, timedelta, timezone

from bson import ObjectId
from fastapi import HTTPException
from pymongo import ASCENDING, DESCENDING

from api.database import get_mongo_db
from api.services.analytics import _query
from api.services.intelligence_store import get_item


OFFSETS = {"daily": timedelta(days=1), "weekly": timedelta(days=7), "monthly": timedelta(days=30)}


def _report_data(query: dict) -> dict:
    conditions = ["a.publish_time >= now() - INTERVAL 7 DAY"]
    params = {}
    if query.get("query"):
        conditions.append("a.title ILIKE {query:String}")
        params["query"] = f"%{query['query']}%"
    for field in ("source", "category"):
        if query.get(field):
            conditions.append(f"a.{field} = {{{field}:String}}")
            params[field] = query[field]
    if query.get("entity"):
        conditions.append("a.url_hash IN (SELECT url_hash FROM newspulse.raw_article_entities WHERE lowerUTF8(entity) = lowerUTF8({entity:String}))")
        params["entity"] = query["entity"]
    if query.get("keyword"):
        conditions.append("a.url_hash IN (SELECT url_hash FROM newspulse.raw_article_keywords WHERE lowerUTF8(keyword) = lowerUTF8({keyword:String}))")
        params["keyword"] = query["keyword"]
    if query.get("sentiment"):
        conditions.append("ifNull(s.sentiment_label, 'neutral') = {sentiment:String}")
        params["sentiment"] = query["sentiment"]
    where = " AND ".join(conditions)
    rows = _query(
        "SELECT a.source, countDistinct(a.url_hash) AS article_count FROM newspulse.raw_articles AS a FINAL "
        "LEFT JOIN (SELECT url_hash, argMax(sentiment_label, loaded_at) AS sentiment_label "
        "FROM newspulse.raw_article_sentiment GROUP BY url_hash) AS s USING (url_hash) "
        f"WHERE {where} GROUP BY a.source ORDER BY article_count DESC LIMIT 20",
        params,
    )
    citations = _query(
        "SELECT a.url_hash AS article_id, a.title, a.url, a.source, a.publish_time AS published_at "
        "FROM newspulse.raw_articles AS a FINAL LEFT JOIN (SELECT url_hash, argMax(sentiment_label, loaded_at) AS sentiment_label "
        "FROM newspulse.raw_article_sentiment GROUP BY url_hash) AS s USING (url_hash) "
        f"WHERE {where} ORDER BY a.publish_time DESC LIMIT 10",
        params,
    )
    return {
        "article_count": sum(int(row["article_count"]) for row in rows),
        "source_count": len(rows),
        "chart": {"type": "bar", "title": "Articles by source", "unit": "articles", "points": [{"label": row["source"], "value": int(row["article_count"])} for row in rows]},
        "citations": citations,
    }


async def ensure_indexes() -> None:
    collection = get_mongo_db().intelligence_reports
    await collection.create_index([("owner_id", ASCENDING), ("created_at", DESCENDING)])
    await collection.create_index("expires_at", expireAfterSeconds=0)


def _serialize(document: dict) -> dict:
    return {**{key: value for key, value in document.items() if key not in {"_id", "owner_id"}}, "id": str(document["_id"])}


async def generate(owner_id: str, saved_query_id: str) -> dict:
    query = await get_item("saved_queries", owner_id, saved_query_id)
    data = _report_data(query)
    now = datetime.now(timezone.utc)
    document = {
        "owner_id": owner_id, "saved_query_id": saved_query_id,
        "name": query["name"], "criteria": {key: query.get(key) for key in ("query", "source", "category", "entity", "keyword", "sentiment") if query.get(key)},
        **data, "created_at": now, "expires_at": now + timedelta(days=30),
    }
    result = await get_mongo_db().intelligence_reports.insert_one(document)
    document["_id"] = result.inserted_id
    return _serialize(document)


async def list_reports(owner_id: str) -> list[dict]:
    rows = await get_mongo_db().intelligence_reports.find({"owner_id": owner_id}).sort("created_at", DESCENDING).to_list(length=100)
    return [_serialize(row) for row in rows]


async def run_due(limit: int = 50) -> dict:
    db = get_mongo_db()
    now = datetime.now(timezone.utc)
    due = await db.intelligence_saved_queries.find({"enabled": True, "next_run_at": {"$lte": now}}).sort("next_run_at", ASCENDING).to_list(length=limit)
    generated = 0
    for query in due:
        schedule = query.get("schedule", "none")
        if schedule not in OFFSETS:
            continue
        await generate(query["owner_id"], str(query["_id"]))
        await db.intelligence_saved_queries.update_one({"_id": query["_id"], "next_run_at": {"$lte": now}}, {"$set": {"next_run_at": now + OFFSETS[schedule], "updated_at": now}})
        generated += 1
    return {"processed": len(due), "generated": generated}


async def get_report(owner_id: str, report_id: str) -> dict:
    if not ObjectId.is_valid(report_id):
        raise HTTPException(status_code=404, detail="Report not found")
    document = await get_mongo_db().intelligence_reports.find_one({"_id": ObjectId(report_id), "owner_id": owner_id})
    if document is None:
        raise HTTPException(status_code=404, detail="Report not found")
    return _serialize(document)
