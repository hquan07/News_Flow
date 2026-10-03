"""Apply allowlisted retention policies configured by operators."""

import os
from datetime import datetime, timedelta

import clickhouse_connect
from airflow import DAG
from airflow.operators.python import PythonOperator, get_current_context
from pymongo import MongoClient


DATASETS = {
    "articles": ("newspulse.raw_articles", "publish_time"),
    "social": ("newspulse.social_sentiment_metrics", "publish_time"),
    "keywords": ("newspulse.raw_article_keywords", "loaded_at"),
    "entities": ("newspulse.raw_article_entities", "loaded_at"),
    "sentiment": ("newspulse.raw_article_sentiment", "loaded_at"),
}


def apply_retention():
    requested = str((get_current_context()["dag_run"].conf or {}).get("dataset", ""))
    names = [requested] if requested else list(DATASETS)
    mongo = MongoClient(os.environ.get("MONGO_URI", "mongodb://mongo:27017"), serverSelectionTimeoutMS=3000)
    clickhouse = clickhouse_connect.get_client(
        host=os.environ.get("CLICKHOUSE_HOST", "clickhouse"), port=int(os.environ.get("CLICKHOUSE_PORT", "8123")),
        username=os.environ.get("CLICKHOUSE_USER", "admin"), password=os.environ.get("CLICKHOUSE_PASSWORD", ""),
        database=os.environ.get("CLICKHOUSE_DB", "newspulse"),
    )
    try:
        database = mongo[os.environ.get("MONGO_DB", "newspulse")]
        for name in names:
            if name not in DATASETS:
                raise ValueError("Unknown retention dataset")
            policy = database.retention_policies.find_one({"dataset": name}) or {}
            if not policy.get("enabled"):
                continue
            days = max(7, min(int(policy.get("retention_days", 365)), 3650))
            table, column = DATASETS[name]
            clickhouse.command(
                f"ALTER TABLE {table} DELETE WHERE {column} < now() - toIntervalDay({{days:UInt32}})",
                parameters={"days": days},
            )
    finally:
        mongo.close()
        clickhouse.close()


with DAG(
    dag_id="newspulse_retention",
    default_args={"owner": "newspulse", "retries": 1, "retry_delay": timedelta(minutes=10)},
    description="Apply configured ClickHouse retention policies",
    schedule_interval="0 3 * * 0", start_date=datetime(2026, 1, 1),
    catchup=False, max_active_runs=1, tags=["retention", "storage"],
) as dag:
    PythonOperator(task_id="apply_retention", python_callable=apply_retention)
