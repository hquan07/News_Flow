"""Replay one warehouse article through Kafka and downstream NLP."""

import os
from datetime import datetime, timedelta

import clickhouse_connect
from airflow import DAG
from airflow.operators.python import PythonOperator, get_current_context
from kafka_utils.producer import ArticleProducer


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
    with ArticleProducer(os.environ.get("KAFKA_BOOTSTRAP_SERVERS", "kafka:9092")) as producer:
        if not producer.send_article(article):
            raise RuntimeError(f"Could not replay article {article_id}")


with DAG(
    dag_id="newspulse_article_replay",
    default_args={"owner": "newspulse", "retries": 1, "retry_delay": timedelta(minutes=2)},
    description="Replay one article through Kafka for enrichment recovery",
    schedule_interval=None,
    start_date=datetime(2026, 1, 1), catchup=False, max_active_runs=2,
    tags=["replay", "lineage"],
) as dag:
    PythonOperator(task_id="replay_article", python_callable=replay_article)
