import os
import requests
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

# Assume these are set in Airflow Variables or environment variables in a real scenario
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN', 'YOUR_TELEGRAM_BOT_TOKEN_HERE')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID', 'YOUR_TELEGRAM_CHAT_ID_HERE')

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

    if TELEGRAM_BOT_TOKEN == 'YOUR_TELEGRAM_BOT_TOKEN_HERE':
        print("Mock execution: Telegram Bot Token not configured.")
        print("Message that would have been sent:")
        print(message)
        return

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "HTML"
    }
    
    try:
        response = requests.post(url, json=payload)
        response.raise_for_status()
        print("Telegram report sent successfully!")
    except Exception as e:
        print(f"Failed to send Telegram report: {e}")
        raise

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
