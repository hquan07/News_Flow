from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.bash import BashOperator
from airflow.operators.python import ShortCircuitOperator, get_current_context
from pymongo import MongoClient
import os

default_args = {
    "owner": "newspulse",
    "depends_on_past": False,
    "email_on_failure": False,
    "retries": 2,
    "retry_delay": timedelta(minutes=5),
    "execution_timeout": timedelta(minutes=20),
}

SPIDERS = [
    "vnexpress", "tuoitre", "thanhnien", "tienphong", "dantri", "laodong",
    "voz_forum", "reddit_vn", "youtube_comments"
]
DEFAULT_RATE_LIMIT_SECONDS = float(
    os.environ.get("DEFAULT_CRAWL_RATE_LIMIT_SECONDS", "0.5")
)

SCRAPY_CMD = (
    "cd /opt/airflow/crawlers && "
    "scrapy crawl {spider} "
    "-s KAFKA_BOOTSTRAP_SERVERS=$KAFKA_BOOTSTRAP_SERVERS "
    "-s MONGO_URI=$MONGO_URI "
    "-s MONGO_DB=$MONGO_DB "
    "-s LOG_LEVEL=INFO"
)


def source_is_enabled(spider: str) -> bool:
    context = get_current_context()
    dag_run = context.get("dag_run")
    requested = (dag_run.conf or {}).get("spider") if dag_run else None
    if requested and requested not in ("all", spider):
        return False
    client = MongoClient(
        os.environ.get("MONGO_URI", "mongodb://mongo:27017"),
        serverSelectionTimeoutMS=3000,
    )
    try:
        database = client[os.environ.get("MONGO_DB", "newspulse")]
        override = database.source_settings.find_one({"spider_name": spider}) or {}
        context["ti"].xcom_push(
            key="rate_limit_seconds",
            value=float(override.get("rate_limit_seconds", DEFAULT_RATE_LIMIT_SECONDS)),
        )
        return override.get("enabled", True)
    finally:
        client.close()

with DAG(
    dag_id="newspulse_crawl",
    default_args=default_args,
    description="Crawl Vietnamese news sources every 10 minutes",
    schedule="*/10 * * * *",
    start_date=datetime(2024, 1, 1),
    catchup=False,
    max_active_runs=1,
    tags=["newspulse", "crawl", "phase1"],
) as dag:

    tasks = {}
    for spider in SPIDERS:
        enabled = ShortCircuitOperator(
            task_id=f"source_enabled_{spider}",
            python_callable=source_is_enabled,
            op_kwargs={"spider": spider},
        )
        tasks[spider] = BashOperator(
            task_id=f"crawl_{spider}",
            bash_command=(
                SCRAPY_CMD.format(spider=spider)
                + f' -s DOWNLOAD_DELAY="{{{{ ti.xcom_pull(task_ids=\'source_enabled_{spider}\', key=\'rate_limit_seconds\') or 0.5 }}}}"'
            ),
        )
        enabled >> tasks[spider]

    # Health check
    verify_kafka = BashOperator(
        task_id="verify_kafka",
        bash_command=(
            'python -c "'
            "from kafka import KafkaConsumer;"
            "c = KafkaConsumer(bootstrap_servers='$KAFKA_BOOTSTRAP_SERVERS', "
            "consumer_timeout_ms=5000, auto_offset_reset='latest');"
            "c.subscribe(pattern='news.*');"
            "msgs = list(c);"
            "print(f'Messages in Kafka: {len(msgs)}');"
            "c.close()"
            '"'
        ),
        trigger_rule="all_done",
    )

    # All spiders run in parallel, then verify
    for task in tasks.values():
        task >> verify_kafka
