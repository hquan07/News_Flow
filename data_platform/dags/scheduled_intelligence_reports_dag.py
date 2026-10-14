"""Generate due owner-scoped reports and archive selected exports."""

import os
from datetime import datetime, timedelta, timezone

import clickhouse_connect
from airflow import DAG
from airflow.operators.python import PythonOperator
from pymongo import MongoClient

from integrations.cloudvault import CloudVaultError
from integrations.cloudvault_reports import upload_intelligence_report


def _cloudvault_enabled() -> bool:
    return os.environ.get("CLOUDVAULT_REPORT_UPLOAD_ENABLED", "false").lower() == "true"


def _run_identity() -> tuple[str, str]:
    """Use Airflow's stable run identity so task retries reuse one upload."""
    try:
        from airflow.operators.python import get_current_context

        context = get_current_context()
    except Exception:
        context = {}
    logical = context.get("logical_date") or context.get("data_interval_end")
    if logical is None:
        logical = datetime.now(timezone.utc)
    logical_date = logical.isoformat() if hasattr(logical, "isoformat") else str(logical)
    source_run_id = str(context.get("run_id") or f"manual:{logical_date}")
    return source_run_id, logical_date


def _archive_error(error: CloudVaultError) -> dict:
    return {
        "status": "failed",
        "error_code": error.code,
        "http_status": error.status_code,
        "retriable": error.retriable,
        "updated_at": datetime.utcnow(),
    }


def generate_due_reports():
    now = datetime.utcnow()
    source_run_id, logical_date = _run_identity()
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
            report_key = {
                "saved_query_id": str(query["_id"]),
                "source_run_id": source_run_id,
            }
            report = database.intelligence_reports.find_one(report_key)
            if report is None:
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
                report = {
                    **report_key,
                    "logical_date": logical_date,
                    "owner_id": query["owner_id"],
                    "saved_query_id": str(query["_id"]),
                    "name": query["name"],
                    "criteria": {key: query.get(key) for key in ("query", "source", "category", "entity", "keyword", "sentiment") if query.get(key)},
                    "article_count": sum(int(row["article_count"]) for row in rows),
                    "source_count": len(rows),
                    "chart": {"type": "bar", "title": "Articles by source", "unit": "articles", "points": [{"label": row["source"], "value": int(row["article_count"])} for row in rows]},
                    "citations": citations,
                    "created_at": now,
                    "expires_at": now + timedelta(days=30),
                    "cloudvault_archive": {"status": "pending", "updated_at": now}
                    if query.get("cloudvault_export_enabled") and _cloudvault_enabled()
                    else {"status": "disabled", "updated_at": now},
                }
                inserted = database.intelligence_reports.insert_one(report)
                report["_id"] = inserted.inserted_id

            should_archive = query.get("cloudvault_export_enabled") and _cloudvault_enabled()
            archive = report.get("cloudvault_archive") or {}
            if should_archive and archive.get("status") != "uploaded":
                try:
                    result = upload_intelligence_report(
                        report,
                        owner_id=query["owner_id"],
                        logical_date=logical_date,
                        source_run_id=source_run_id,
                    )
                except CloudVaultError as error:
                    database.intelligence_reports.update_one(
                        {"_id": report["_id"]},
                        {"$set": {"cloudvault_archive": _archive_error(error)}},
                    )
                    raise
                database.intelligence_reports.update_one(
                    {"_id": report["_id"]},
                    {"$set": {"cloudvault_archive": {**result, "updated_at": datetime.utcnow()}}},
                )
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
