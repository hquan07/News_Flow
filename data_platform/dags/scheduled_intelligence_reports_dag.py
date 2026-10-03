"""Generate due owner-scoped saved-query reports once per hour."""

import asyncio
from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.python import PythonOperator


def generate_due_reports():
    from api.services.scheduled_reports import run_due
    return asyncio.run(run_due(limit=100))


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
