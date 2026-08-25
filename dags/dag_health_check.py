import json
from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.python import PythonOperator

from monitoring.health_monitor import airflow_health_check, run_checks

default_args = {
    "owner": "newspulse",
    "depends_on_past": False,
    "email_on_failure": True,
    "email_on_retry": False,
    "retries": 1,
    "retry_delay": timedelta(minutes=2),
}


def check_data_freshness(**kwargs):
    from datetime import timezone

    import psycopg2
    from pymongo import MongoClient

    alerts = []

    # Check MongoDB — bài viết mới nhất
    try:
        client = MongoClient("mongodb://mongo:27017", serverSelectionTimeoutMS=5000)
        db = client["newspulse"]
        latest = db["articles_raw"].find_one(sort=[("crawled_at", -1)])

        if latest and "crawled_at" in latest:
            crawled_at = latest["crawled_at"]
            if hasattr(crawled_at, "replace"):
                crawled_at = crawled_at.replace(tzinfo=timezone.utc)
            age_hours = (datetime.now(timezone.utc) - crawled_at).total_seconds() / 3600

            if age_hours > 2:
                alerts.append(
                    f"MongoDB: No new articles in {age_hours:.1f} hours "
                    f"(last crawl: {latest['crawled_at']})"
                )
        client.close()
    except Exception as e:
        alerts.append(f"MongoDB freshness check failed: {e}")

    # Check PostgreSQL — fact table freshness
    try:
        conn = psycopg2.connect(
            host="postgres", port=5432,
            user="newspulse", password="newspulse",
            dbname="newspulse", connect_timeout=5,
        )
        cur = conn.cursor()
        cur.execute("""
            SELECT MAX(dt.full_date) as latest_date
            FROM warehouse.fact_article fa
            JOIN warehouse.dim_time dt ON fa.time_id = dt.time_id
        """)
        row = cur.fetchone()
        if row and row[0]:
            days_behind = (datetime.now().date() - row[0]).days
            if days_behind > 1:
                alerts.append(
                    f"PostgreSQL warehouse: Data is {days_behind} days behind "
                    f"(latest: {row[0]})"
                )
        cur.close()
        conn.close()
    except Exception as e:
        alerts.append(f"PostgreSQL freshness check failed: {e}")

    if alerts:
        raise RuntimeError(
            "Data freshness issues detected:\n"
            + "\n".join(f"  ⚠️ {a}" for a in alerts)
        )

    kwargs["ti"].xcom_push(key="freshness_status", value="ok")


def check_kafka_lag(**kwargs):
    from kafka import KafkaAdminClient, KafkaConsumer

    LAG_THRESHOLD = 1000

    try:
        consumer = KafkaConsumer(
            bootstrap_servers="kafka:9092",
            group_id="newspulse-spark",
        )

        admin = KafkaAdminClient(bootstrap_servers="kafka:9092")
        topics = [t for t in admin.list_topics() if not t.startswith("__")]

        lag_report = {}
        total_lag = 0

        for topic in topics:
            partitions = consumer.partitions_for_topic(topic)
            if not partitions:
                continue

            from kafka import TopicPartition

            for p in partitions:
                tp = TopicPartition(topic, p)
                consumer.assign([tp])
                consumer.seek_to_end(tp)
                end_offset = consumer.position(tp)

                committed = consumer.committed(tp)
                if committed is not None:
                    lag = end_offset - committed
                    lag_report[f"{topic}:{p}"] = lag
                    total_lag += lag

        consumer.close()
        admin.close()

        kwargs["ti"].xcom_push(key="kafka_lag", value=lag_report)
        kwargs["ti"].xcom_push(key="total_lag", value=total_lag)

        if total_lag > LAG_THRESHOLD:
            raise RuntimeError(
                f"Kafka consumer lag too high: {total_lag} messages total.\n"
                f"Detail: {json.dumps(lag_report, indent=2)}"
            )

    except ImportError:
        raise RuntimeError("kafka-python not installed")


# DAG Definition
with DAG(
    dag_id="newspulse_health_check",
    default_args=default_args,
    description="Kiểm tra sức khỏe hệ thống NewsPulse mỗi 15 phút",
    schedule="*/15 * * * *",
    start_date=datetime(2025, 1, 1),
    catchup=False,
    tags=["monitoring", "health"],
    max_active_runs=1,
) as dag:

    t_service_health = PythonOperator(
        task_id="check_service_health",
        python_callable=airflow_health_check,
    )

    t_data_freshness = PythonOperator(
        task_id="check_data_freshness",
        python_callable=check_data_freshness,
    )

    t_kafka_lag = PythonOperator(
        task_id="check_kafka_lag",
        python_callable=check_kafka_lag,
    )

    # Chạy song song — mỗi check độc lập
    [t_service_health, t_data_freshness, t_kafka_lag]