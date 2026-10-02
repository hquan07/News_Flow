import hashlib
import logging
import os
from datetime import datetime, timedelta

from airflow.decorators import dag, task

logger = logging.getLogger(__name__)

default_args = {
    "owner": "newspulse",
    "depends_on_past": False,
    "email_on_failure": False,
    "retries": 1,
    "retry_delay": timedelta(minutes=5),
}


def _hour_key(value) -> str:
    return value.strftime("%Y%m%d%H")


def _keyword_key(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:12]


@dag(
    dag_id="anomaly_alerting_dag",
    default_args=default_args,
    description="Kiểm tra Trend đột biến và Sentiment tiêu cực, gửi cảnh báo qua Telegram",
    schedule="*/30 * * * *",
    start_date=datetime(2025, 1, 1),
    catchup=False,
    tags=["alerting", "monitoring"],
    max_active_runs=1,
)
def alerting_pipeline():

    @task
    def detect_anomalies_and_alert():
        import clickhouse_connect

        from monitoring.alert_dispatcher import AlertEvent, send_telegram_events

        try:
            client = clickhouse_connect.get_client(
                host=os.getenv("CLICKHOUSE_HOST", "clickhouse"),
                port=int(os.getenv("CLICKHOUSE_PORT", "8123")),
                username=os.getenv("CLICKHOUSE_USER", "admin"),
                password=os.getenv("CLICKHOUSE_PASSWORD", ""),
                database=os.getenv("CLICKHOUSE_DB", "newspulse"),
            )
            alerts: list[AlertEvent] = []

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
            for _, row in volume_results.iterrows():
                surge = round(row["article_count"] / max(row["avg_count"], 1), 1)
                hour_slot = row["hour_slot"]
                alerts.append(
                    AlertEvent(
                        alert_id=f"volume:{_hour_key(hour_slot)}",
                        alert_type="volume_spike",
                        severity="warning",
                        title="Bão tin tức (volume spike)",
                        details=(
                            f"Khung giờ {hour_slot.strftime('%H:%M %d/%m')}",
                            f"{row['article_count']} tin; trung bình {row['avg_count']}",
                            f"Tăng {surge}x so với trung bình",
                        ),
                    )
                )

            trend_query = """
                SELECT
                    keyword,
                    count() AS current_count,
                    (SELECT count()/24 FROM newspulse.raw_article_keywords
                     WHERE loaded_at >= now() - INTERVAL 24 HOUR
                       AND keyword = k.keyword) as avg_24h,
                    toStartOfHour(now()) AS hour_slot
                FROM newspulse.raw_article_keywords k
                WHERE loaded_at >= now() - INTERVAL 1 HOUR
                GROUP BY keyword, hour_slot
                HAVING current_count > 10 AND current_count > avg_24h * 2.0
                ORDER BY current_count DESC
                LIMIT 5
            """
            trend_results = client.query_df(trend_query)
            for _, row in trend_results.iterrows():
                keyword = str(row["keyword"])
                alerts.append(
                    AlertEvent(
                        alert_id=(
                            f"trend:{_keyword_key(keyword)}:"
                            f"{_hour_key(row['hour_slot'])}"
                        ),
                        alert_type="trend_spike",
                        severity="warning",
                        title=f"Trend đột biến: {keyword}",
                        details=(
                            f"{row['current_count']} tin trong giờ qua",
                            f"Trung bình 24h: {row['avg_24h']:.1f} tin/giờ",
                        ),
                    )
                )

            sentiment_query = """
                SELECT
                    sentiment_label,
                    count() AS count,
                    toStartOfHour(now()) AS hour_slot
                FROM newspulse.raw_article_sentiment
                WHERE loaded_at >= now() - INTERVAL 1 HOUR
                GROUP BY sentiment_label, hour_slot
            """
            sentiment_results = client.query_df(sentiment_query)
            if not sentiment_results.empty:
                total = sentiment_results["count"].sum()
                negative_rows = sentiment_results[
                    sentiment_results["sentiment_label"] == "negative"
                ]
                if not negative_rows.empty:
                    negative = negative_rows.iloc[0]
                    negative_count = negative["count"]
                    negative_pct = negative_count / total * 100
                    if negative_pct > 30 and total > 50:
                        alerts.append(
                            AlertEvent(
                                alert_id=(
                                    f"sentiment:negative:"
                                    f"{_hour_key(negative['hour_slot'])}"
                                ),
                                alert_type="negative_sentiment",
                                severity="critical",
                                title="Tâm lý tiêu cực tăng cao",
                                details=(
                                    f"Tỷ lệ tiêu cực: {negative_pct:.1f}%",
                                    f"{negative_count}/{total} tin trong giờ qua",
                                ),
                            )
                        )

            sent_count = send_telegram_events(alerts)
            if sent_count:
                logger.info("Đã gửi %s cảnh báo Telegram mới.", sent_count)
            elif alerts:
                logger.info("Các cảnh báo đang trong thời gian cooldown.")
            else:
                logger.info("Hệ thống ổn định, không có cảnh báo nào.")

        except Exception:
            logger.exception("Lỗi khi chạy Alerting DAG")
            raise

    detect_anomalies_and_alert()


dag = alerting_pipeline()
