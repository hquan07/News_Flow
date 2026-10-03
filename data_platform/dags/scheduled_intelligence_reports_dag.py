"""Generate due owner-scoped saved-query reports once per hour."""

import os
from datetime import datetime, timedelta

import clickhouse_connect
from airflow import DAG
from airflow.operators.python import PythonOperator
from pymongo import MongoClient


def generate_due_reports():
    now = datetime.utcnow()
    mongo = MongoClient(os.environ.get("MONGO_URI", "mongodb://mongo:27017"), serverSelectionTimeoutMS=3000)
    clickhouse = clickhouse_connect.get_client(
        host=os.environ.get("CLICKHOUSE_HOST", "clickhouse"), port=int(os.environ.get("CLICKHOUSE_PORT", "8123")),
        username=os.environ.get("CLICKHOUSE_USER", "admin"), password=os.environ.get("CLICKHOUSE_PASSWORD", ""),
        database=os.environ.get("CLICKHOUSE_DB", "newspulse"),
    )
    offsets = {"daily": timedelta(days=1), "weekly": timedelta(days=7), "monthly": timedelta(days=30)}
    generated = 0
    try:
        database = mongo[os.environ.get("MONGO_DB", "newspulse")]
        due = list(database.intelligence_saved_queries.find({"enabled": True, "next_run_at": {"$lte": now}}).sort("next_run_at", 1).limit(100))
        for query in due:
            schedule = query.get("schedule", "none")
            if schedule not in offsets:
                continue
            conditions = ["a.publish_time >= now() - INTERVAL 7 DAY"]
            params = {}
            if query.get("query"):
                conditions.append("a.title ILIKE {query:String}")
                params["query"] = f"%{query['query']}%"
            for field in ("source", "category"):
                if query.get(field):
                    conditions.append(f"a.{field} = {{{field}:String}}")
                    params[field] = query[field]
            where = " AND ".join(conditions)
            rows = list(clickhouse.query(
                "SELECT a.source, countDistinct(a.url_hash) AS article_count FROM newspulse.raw_articles AS a FINAL "
                f"WHERE {where} GROUP BY a.source ORDER BY article_count DESC LIMIT 20",
                parameters=params,
            ).named_results())
            citations = list(clickhouse.query(
                "SELECT a.url_hash AS article_id, a.title, a.url, a.source, a.publish_time AS published_at "
                f"FROM newspulse.raw_articles AS a FINAL WHERE {where} ORDER BY a.publish_time DESC LIMIT 10",
                parameters=params,
            ).named_results())
            database.intelligence_reports.insert_one({
                "owner_id": query["owner_id"], "saved_query_id": str(query["_id"]), "name": query["name"],
                "criteria": {key: query.get(key) for key in ("query", "source", "category", "entity", "keyword", "sentiment") if query.get(key)},
                "article_count": sum(int(row["article_count"]) for row in rows), "source_count": len(rows),
                "chart": {"type": "bar", "title": "Articles by source", "unit": "articles", "points": [{"label": row["source"], "value": int(row["article_count"])} for row in rows]},
                "citations": citations, "created_at": now, "expires_at": now + timedelta(days=30),
            })
            database.intelligence_saved_queries.update_one({"_id": query["_id"], "next_run_at": {"$lte": now}}, {"$set": {"next_run_at": now + offsets[schedule], "updated_at": now}})
            generated += 1
        return {"processed": len(due), "generated": generated}
    finally:
        mongo.close()
        clickhouse.close()


with DAG(
    dag_id="scheduled_intelligence_reports",
    default_args={"owner": "newspulse", "retries": 2, "retry_delay": timedelta(minutes=5)},
    description="Generate due personal intelligence reports",
    schedule_interval="15 * * * *",
    start_date=datetime(2026, 1, 1),
    catchup=False,
    max_active_runs=1,
    tags=["reports", "intelligence"],
) as dag:
    PythonOperator(task_id="generate_due_reports", python_callable=generate_due_reports)
