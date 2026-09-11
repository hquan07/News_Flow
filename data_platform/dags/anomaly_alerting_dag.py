from datetime import datetime, timedelta
import logging
from airflow.decorators import dag, task

logger = logging.getLogger(__name__)

default_args = {
    "owner": "newspulse",
    "depends_on_past": False,
    "email_on_failure": False,
    "retries": 1,
    "retry_delay": timedelta(minutes=5),
}

@dag(
    dag_id="anomaly_alerting_dag",
    default_args=default_args,
    description="Kiểm tra Trend đột biến và Sentiment tiêu cực, gửi cảnh báo qua Telegram",
    schedule="*/30 * * * *",  # Chạy mỗi 30 phút
    start_date=datetime(2025, 1, 1),
    catchup=False,
    tags=["alerting", "monitoring"],
    max_active_runs=1,
)
def alerting_pipeline():

    @task
    def detect_anomalies_and_alert():
        import clickhouse_connect
        import sys
        
        # Load telegram alert module
        sys.path.append("/opt/airflow/dags/infrastructure/monitoring") # Adjust path as needed
        try:
            from infrastructure.monitoring.telegram_alert import send_telegram_alert
        except ImportError:
            logger.error("Could not import Telegram Alert module.")
            return

        try:
            client = clickhouse_connect.get_client(host="clickhouse", port=8123, username="default", password="")
            
            alerts = []
            
            # 0. Phát hiện Volume Spike (Bão tin tức)
            volume_query = """
                WITH hourly AS (
                    SELECT toStartOfHour(publish_time) AS hour_slot, count() AS cnt 
                    FROM newspulse.raw_articles 
                    WHERE publish_time >= now() - INTERVAL 7 DAY GROUP BY hour_slot
                ), stats AS (
                    SELECT avg(cnt) AS avg_cnt, stddevPop(cnt) AS std_cnt FROM hourly
                ) 
                SELECT h.hour_slot, h.cnt AS article_count, toInt32(s.avg_cnt) AS avg_count 
                FROM hourly h, stats s 
                WHERE h.cnt > s.avg_cnt + 2.0 * s.std_cnt 
                  AND h.hour_slot >= toStartOfHour(now() - INTERVAL 2 HOUR)
                ORDER BY h.hour_slot DESC
            """
            volume_results = client.query_df(volume_query)
            if not volume_results.empty:
                vol_msg = "🌪 <b>BÃO TIN TỨC (VOLUME SPIKE)</b>:\n"
                for _, row in volume_results.iterrows():
                    surge = round(row['article_count'] / max(row['avg_count'], 1), 1)
                    vol_msg += f"- Khung giờ <b>{row['hour_slot'].strftime('%H:%M %d/%m')}</b>: {row['article_count']} tin (Tăng <b>{surge}x</b> so với TB {row['avg_count']})\n"
                alerts.append(vol_msg)

            # 1. Phát hiện Trending Spike (Z-Score > 2.0 cho Keyword)
            # Truy vấn số lượng keyword xuất hiện trong 1 giờ qua so với trung bình 24h
            trend_query = """
                SELECT 
                    keyword,
                    count() AS current_count,
                    (SELECT count()/24 FROM newspulse.raw_article_keywords WHERE loaded_at >= now() - INTERVAL 24 HOUR AND keyword = k.keyword) as avg_24h
                FROM newspulse.raw_article_keywords k
                WHERE loaded_at >= now() - INTERVAL 1 HOUR
                GROUP BY keyword
                HAVING current_count > 10 AND current_count > avg_24h * 2.0
                ORDER BY current_count DESC
                LIMIT 5
            """
            trend_results = client.query_df(trend_query)
            
            if not trend_results.empty:
                trend_msg = "🔥 <b>TREND ĐỘT BIẾN</b>:\n"
                for _, row in trend_results.iterrows():
                    trend_msg += f"- <b>{row['keyword']}</b>: {row['current_count']} tin (TB: {row['avg_24h']:.1f}/h)\n"
                alerts.append(trend_msg)
                
            # 2. Phát hiện Sentiment Tiêu Cực (Quá 30% tin tức trong 1 giờ)
            sentiment_query = """
                SELECT 
                    sentiment_label,
                    count() as count
                FROM newspulse.raw_article_sentiment
                WHERE loaded_at >= now() - INTERVAL 1 HOUR
                GROUP BY sentiment_label
            """
            sent_results = client.query_df(sentiment_query)
            if not sent_results.empty:
                total = sent_results['count'].sum()
                negative_row = sent_results[sent_results['sentiment_label'] == 'negative']
                if not negative_row.empty:
                    neg_count = negative_row['count'].values[0]
                    if neg_count / total > 0.3 and total > 50:
                        alerts.append(f"📉 <b>TÂM LÝ TIÊU CỰC TĂNG CAO</b>:\n- Tỷ lệ: {neg_count/total*100:.1f}%\n- Số tin: {neg_count}/{total}")

            # Gửi cảnh báo tổng hợp
            if alerts:
                final_msg = "🚨 <b>NEWSPULSE ALERT REPORT</b> 🚨\n\n" + "\n".join(alerts)
                send_telegram_alert(final_msg)
                logger.info(f"Đã gửi cảnh báo: {final_msg}")
            else:
                logger.info("Hệ thống ổn định, không có cảnh báo nào.")
                
        except Exception as e:
            logger.error(f"Lỗi khi chạy Alerting DAG: {e}")

    # Chạy task
    detect_anomalies_and_alert()

dag = alerting_pipeline()
