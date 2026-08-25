from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.python import PythonOperator

from data_quality.run_validations import (
    airflow_validate_raw,
    airflow_validate_staging,
    airflow_validate_warehouse,
    run_all,
)

default_args = {
    "owner": "newspulse",
    "depends_on_past": False,
    "email_on_failure": True,
    "email_on_retry": False,
    "retries": 1,
    "retry_delay": timedelta(minutes=5),
}


def generate_dq_report(**kwargs):
    import json
    from loguru import logger

    report = run_all()

    summary = report["summary"]
    logger.info(
        f"Data Quality Summary: {summary['overall']} — "
        f"{summary['passed']}/{summary['total_checks']} checks passed"
    )

    # Log failed checks
    for layer_name, layer_data in report["layers"].items():
        for check in layer_data["checks"]:
            if not check["passed"]:
                logger.warning(f"FAILED: {check['check']} (value={check.get('value')})")

    kwargs["ti"].xcom_push(key="dq_full_report", value=report)

    if summary["overall"] != "PASS":
        logger.error(f"Data quality check FAILED: {summary['failed']} checks failed")


with DAG(
    dag_id="newspulse_data_quality",
    default_args=default_args,
    description="Data quality checks cho tất cả schema layers",
    schedule=None,  # Triggered after ELT, hoặc chạy manual
    start_date=datetime(2025, 1, 1),
    catchup=False,
    tags=["data-quality", "monitoring"],
    max_active_runs=1,
) as dag:

    t_raw = PythonOperator(
        task_id="validate_raw_layer",
        python_callable=airflow_validate_raw,
    )

    t_staging = PythonOperator(
        task_id="validate_staging_layer",
        python_callable=airflow_validate_staging,
    )

    t_warehouse = PythonOperator(
        task_id="validate_warehouse_layer",
        python_callable=airflow_validate_warehouse,
    )

    t_report = PythonOperator(
        task_id="generate_dq_report",
        python_callable=generate_dq_report,
        trigger_rule="all_done",  # Chạy dù có layer fail
    )

    # Sequential: raw → staging → warehouse → report
    t_raw >> t_staging >> t_warehouse >> t_report