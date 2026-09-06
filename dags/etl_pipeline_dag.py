from datetime import datetime, timedelta
from airflow import DAG
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


# DAG definition
with DAG(
    dag_id="newspulse_elt_pipeline",
    default_args=default_args,
    description="ELT pipeline using dbt for ClickHouse",
    schedule_interval="15 * * * *",  # Every hour at :15
    start_date=datetime(2025, 1, 1),
    catchup=False,
    max_active_runs=1,
    tags=["newspulse", "elt", "dbt", "clickhouse"],
) as dag:

    # Task 1: dbt run (staging, warehouse, mart)
    t_dbt_run = BashOperator(
        task_id="dbt_run",
        bash_command="cd /opt/airflow/warehouse/dbt_project && dbt run",
    )

    # Task 2: dbt test
    t_dbt_test = BashOperator(
        task_id="dbt_test",
        bash_command="cd /opt/airflow/warehouse/dbt_project && dbt test",
    )

    # Task 3: Log summary
    t_log_summary = BashOperator(
        task_id="log_summary",
        bash_command='echo "dbt pipeline completed at $(date)"',
    )


    # Task dependencies
    t_dbt_run >> t_dbt_test >> t_log_summary