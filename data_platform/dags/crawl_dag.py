from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.bash import BashOperator

default_args = {
    "owner": "newspulse",
    "depends_on_past": False,
    "email_on_failure": False,
    "retries": 2,
    "retry_delay": timedelta(minutes=5),
    "execution_timeout": timedelta(minutes=20),
}

SPIDERS = ["vnexpress", "tuoitre", "thanhnien", "tienphong", "dantri", "laodong"]

SCRAPY_CMD = (
    "cd /opt/airflow/crawlers && "
    "scrapy crawl {spider} "
    "-s KAFKA_BOOTSTRAP_SERVERS=$KAFKA_BOOTSTRAP_SERVERS "
    "-s MONGO_URI=$MONGO_URI "
    "-s MONGO_DB=$MONGO_DB "
    "-s LOG_LEVEL=INFO"
)

with DAG(
    dag_id="newspulse_crawl",
    default_args=default_args,
    description="Crawl Vietnamese news sources every 30 minutes",
    schedule="*/30 * * * *",
    start_date=datetime(2024, 1, 1),
    catchup=False,
    max_active_runs=1,
    tags=["newspulse", "crawl", "phase1"],
) as dag:

    tasks = {}
    for spider in SPIDERS:
        tasks[spider] = BashOperator(
            task_id=f"crawl_{spider}",
            bash_command=SCRAPY_CMD.format(spider=spider),
        )

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