"""Replay one warehouse article through Kafka and downstream NLP."""

import json
import os
from datetime import datetime, timedelta

import clickhouse_connect
from airflow import DAG
from airflow.operators.python import PythonOperator, get_current_context
from kafka import KafkaProducer


TOPICS = {
    "sports": "news.sports", "tech": "news.tech", "economy": "news.economy",
    "politics": "news.politics", "entertainment": "news.entertainment",
    "health": "news.health", "education": "news.education", "world": "news.world",
    "law": "news.law",
}


def replay_article():
    article_id = str((get_current_context()["dag_run"].conf or {}).get("article_id", ""))
    if not article_id:
        raise ValueError("article_id is required")
    client = clickhouse_connect.get_client(
        host=os.environ.get("CLICKHOUSE_HOST", "clickhouse"), port=int(os.environ.get("CLICKHOUSE_PORT", "8123")),
        username=os.environ.get("CLICKHOUSE_USER", "admin"), password=os.environ.get("CLICKHOUSE_PASSWORD", ""),
        database=os.environ.get("CLICKHOUSE_DB", "newspulse"),
    )
    try:
        rows = list(client.query(
            "SELECT url, title, content, author, publish_time, crawled_at, source, category "
            "FROM newspulse.raw_articles FINAL WHERE url_hash = {article_id:String} LIMIT 1",
            parameters={"article_id": article_id},
        ).named_results())
    finally:
        client.close()
    if not rows:
        raise ValueError("Article not found")
    article = rows[0]
    article["crawled_time"] = article.pop("crawled_at", None)
    article["replay"] = {"original_article_id": article_id, "replayed_at": datetime.utcnow().isoformat()}
    producer = KafkaProducer(
        bootstrap_servers=os.environ.get("KAFKA_BOOTSTRAP_SERVERS", "kafka:9092"),
        value_serializer=lambda value: json.dumps(value, ensure_ascii=False, default=str).encode(),
        key_serializer=lambda value: value.encode(), acks="all", retries=3,
    )
    try:
        producer.send(TOPICS.get(str(article.get("category", "")).lower(), "news.general"), key=article_id, value=article).get(timeout=15)
        producer.flush()
    finally:
        producer.close()


with DAG(
    dag_id="newspulse_article_replay",
    default_args={"owner": "newspulse", "retries": 1, "retry_delay": timedelta(minutes=2)},
    description="Replay one article through Kafka for enrichment recovery",
    schedule_interval=None,
    start_date=datetime(2026, 1, 1), catchup=False, max_active_runs=2,
    tags=["replay", "lineage"],
) as dag:
    PythonOperator(task_id="replay_article", python_callable=replay_article)
