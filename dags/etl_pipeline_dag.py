from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.operators.bash import BashOperator

# DAG default args
default_args = {
    "owner": "newspulse",
    "depends_on_past": False,
    "email_on_failure": False,
    "email_on_retry": False,
    "retries": 2,
    "retry_delay": timedelta(minutes=5),
    "execution_timeout": timedelta(minutes=30),
}


# Task callables
def _run_migrations():
    from warehouse.run_migrations import run_migrations
    run_migrations()


def _raw_to_staging():
    from warehouse.etl.raw_to_staging import run
    return run()


def _staging_to_warehouse():
    from warehouse.etl.staging_to_warehouse import run
    return run()


def _warehouse_to_mart():
    from warehouse.etl.warehouse_to_mart import run
    run()


# DAG definition
with DAG(
    dag_id="newspulse_elt_pipeline",
    default_args=default_args,
    description="ELT pipeline: raw → staging → warehouse → mart",
    schedule_interval="15 * * * *",  # Every hour at :15
    start_date=datetime(2025, 1, 1),
    catchup=False,
    max_active_runs=1,
    tags=["newspulse", "elt", "phase2"],
) as dag:

    # Task 0: Ensure schema and tables exist
    t_migrations = PythonOperator(
        task_id="run_migrations",
        python_callable=_run_migrations,
    )

    # Task 1: raw → staging
    t_raw_to_staging = PythonOperator(
        task_id="raw_to_staging",
        python_callable=_raw_to_staging,
    )

    # Task 2: staging → warehouse (dims + fact + bridges)
    t_staging_to_warehouse = PythonOperator(
        task_id="staging_to_warehouse",
        python_callable=_staging_to_warehouse,
    )

    # Task 3: warehouse → mart (refresh aggregations)
    t_warehouse_to_mart = PythonOperator(
        task_id="warehouse_to_mart",
        python_callable=_warehouse_to_mart,
    )

    # Task 4: Log summary
    t_log_summary = BashOperator(
        task_id="log_summary",
        bash_command='echo "ELT pipeline completed at $(date)"',
    )


    # Task dependencies
    (
        t_migrations
        >> t_raw_to_staging
        >> t_staging_to_warehouse
        >> t_warehouse_to_mart
        >> t_log_summary
    )