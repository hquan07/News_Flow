from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.python import PythonOperator

# Default arguments for the DAG
default_args = {
    'owner': 'airflow',
    'depends_on_past': False,
    'email_on_failure': False,
    'email_on_retry': False,
    'retries': 1,
    'retry_delay': timedelta(minutes=5),
}

def fetch_metrics():
    """
    Mock function to fetch daily metrics from the data warehouse (PostgreSQL/Elasticsearch).
    In a real implementation, this would connect to the DB and execute aggregation queries.
    """
    return {
        "date": datetime.now().strftime("%Y-%m-%d"),
        "total_news_articles": 150342,
        "total_social_posts": 84392,
        "anomaly_alerts": 12,
        "crawler_success_rate": "98.5%",
        "avg_processing_latency": "140ms"
    }

def format_and_send_telegram_report(**kwargs):
    """
    Formats the fetched metrics into a readable HTML/Markdown message and sends it via Telegram.
    """
    from monitoring.telegram_alert import send_telegram_alert

    metrics = fetch_metrics()
    
    # Format the message using HTML parse mode supported by Telegram
    message = f"""
<b>📊 NewsPulse Intelligence - Daily Report</b>
<i>Date: {metrics['date']}</i>

<b>📈 Volume Processed</b>
• News Articles: {metrics['total_news_articles']:,}
• Social Posts: {metrics['total_social_posts']:,}

<b>🚨 System Health</b>
• Anomaly Alerts: {metrics['anomaly_alerts']}
• Crawler Success Rate: {metrics['crawler_success_rate']}
• Avg Processing Latency: {metrics['avg_processing_latency']}

<i>Generated automatically by Airflow DAG</i>
"""

    send_telegram_alert(message)

with DAG(
    'telegram_daily_report_dag',
    default_args=default_args,
    description='A simple DAG to generate and send daily metrics report via Telegram',
    schedule_interval='0 8 * * *', # Run daily at 08:00 AM
    start_date=datetime(2026, 9, 13),
    catchup=False,
    tags=['reporting', 'telegram'],
) as dag:

    send_report_task = PythonOperator(
        task_id='send_telegram_report',
        python_callable=format_and_send_telegram_report,
        provide_context=True
    )

    send_report_task
