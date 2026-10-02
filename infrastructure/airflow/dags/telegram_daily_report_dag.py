import os
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from airflow import DAG
from airflow.models.taskinstance import TaskInstance
from airflow.operators.python import PythonOperator
from airflow.utils.session import create_session
from pymongo import MongoClient

LOCAL_TIMEZONE = ZoneInfo("Asia/Ho_Chi_Minh")

default_args = {
    "owner": "newspulse",
    "depends_on_past": False,
    "email_on_failure": False,
    "email_on_retry": False,
    "retries": 1,
    "retry_delay": timedelta(minutes=5),
}


def _report_window(report_date: date) -> tuple[datetime, datetime]:
    start_local = datetime.combine(report_date, time.min, tzinfo=LOCAL_TIMEZONE)
    end_local = start_local + timedelta(days=1)
    return start_local.astimezone(timezone.utc), end_local.astimezone(timezone.utc)


def _crawler_task_counts(start_at: datetime, end_at: datetime) -> tuple[int, int]:
    terminal_states = ("success", "failed", "upstream_failed")
    with create_session() as session:
        states = (
            session.query(TaskInstance.state)
            .filter(
                TaskInstance.dag_id == "newspulse_crawl",
                TaskInstance.task_id.like("crawl_%"),
                TaskInstance.start_date >= start_at,
                TaskInstance.start_date < end_at,
                TaskInstance.state.in_(terminal_states),
            )
            .all()
        )
    values = [row[0] for row in states]
    return values.count("success"), len(values)


def _resolve_report_date(context: dict) -> date:
    logical_date = context.get("logical_date")
    if logical_date is None:
        local_now = datetime.now(LOCAL_TIMEZONE)
    else:
        local_now = logical_date.astimezone(LOCAL_TIMEZONE)
    return local_now.date() - timedelta(days=1)


def format_and_send_telegram_report(**context):
    import clickhouse_connect

    from monitoring.daily_report import (
        DailyMetrics,
        count_sent_alerts,
        fetch_clickhouse_daily_metrics,
        format_daily_report,
    )
    from monitoring.telegram_alert import send_telegram_alert

    report_date = _resolve_report_date(context)
    start_at, end_at = _report_window(report_date)

    clickhouse = clickhouse_connect.get_client(
        host=os.getenv("CLICKHOUSE_HOST", "clickhouse"),
        port=int(os.getenv("CLICKHOUSE_PORT", "8123")),
        username=os.getenv("CLICKHOUSE_USER", "admin"),
        password=os.getenv("CLICKHOUSE_PASSWORD", ""),
        database=os.getenv("CLICKHOUSE_DB", "newspulse"),
    )
    try:
        warehouse_metrics = fetch_clickhouse_daily_metrics(
            clickhouse,
            start_at,
            end_at,
        )
    finally:
        clickhouse.close()

    mongo = MongoClient(
        os.getenv("MONGO_URI", "mongodb://mongo:27017"),
        serverSelectionTimeoutMS=3000,
    )
    try:
        anomaly_alerts = count_sent_alerts(
            mongo[os.getenv("MONGO_DB", "newspulse")].telegram_alert_deliveries,
            start_at,
            end_at,
        )
    finally:
        mongo.close()

    crawler_successes, crawler_finished = _crawler_task_counts(start_at, end_at)
    metrics = DailyMetrics(
        report_date=report_date,
        anomaly_alerts=anomaly_alerts,
        crawler_successes=crawler_successes,
        crawler_finished=crawler_finished,
        **warehouse_metrics,
    )
    send_telegram_alert(format_daily_report(metrics))


with DAG(
    dag_id="telegram_daily_report_dag",
    default_args=default_args,
    description="Send the previous day's real NewsPulse metrics to Telegram",
    schedule="0 8 * * *",
    start_date=datetime(2026, 9, 13, tzinfo=LOCAL_TIMEZONE),
    catchup=False,
    tags=["reporting", "telegram"],
) as dag:
    send_report_task = PythonOperator(
        task_id="send_telegram_report",
        python_callable=format_and_send_telegram_report,
    )

    send_report_task
