from dataclasses import dataclass
from datetime import date, datetime


@dataclass(frozen=True)
class DailyMetrics:
    report_date: date
    total_articles: int
    total_social_posts: int
    active_sources: int
    anomaly_alerts: int
    crawler_successes: int
    crawler_finished: int
    avg_crawl_latency_minutes: float

    @property
    def crawler_success_rate(self) -> float | None:
        if not self.crawler_finished:
            return None
        return self.crawler_successes / self.crawler_finished * 100


def fetch_clickhouse_daily_metrics(
    client,
    start_at: datetime,
    end_at: datetime,
) -> dict:
    parameters = {"start_at": start_at, "end_at": end_at}
    article_query = """
        SELECT
            count() AS total_articles,
            uniqExact(source) AS active_sources,
            coalesce(round(avg(crawl_latency_minutes), 1), 0) AS avg_crawl_latency
        FROM newspulse.raw_articles
        WHERE loaded_at >= {start_at:DateTime}
          AND loaded_at < {end_at:DateTime}
    """
    social_query = """
        SELECT count() AS total_social_posts
        FROM newspulse.social_sentiment_metrics
        WHERE loaded_at >= {start_at:DateTime}
          AND loaded_at < {end_at:DateTime}
    """

    article_rows = list(
        client.query(article_query, parameters=parameters).named_results()
    )
    social_rows = list(
        client.query(social_query, parameters=parameters).named_results()
    )
    article = article_rows[0] if article_rows else {}
    social = social_rows[0] if social_rows else {}
    return {
        "total_articles": int(article.get("total_articles") or 0),
        "active_sources": int(article.get("active_sources") or 0),
        "avg_crawl_latency_minutes": float(
            article.get("avg_crawl_latency") or 0
        ),
        "total_social_posts": int(social.get("total_social_posts") or 0),
    }


def count_sent_alerts(collection, start_at: datetime, end_at: datetime) -> int:
    return collection.count_documents(
        {
            "status": "sent",
            "sent_at": {"$gte": start_at, "$lt": end_at},
        }
    )


def format_daily_report(metrics: DailyMetrics) -> str:
    success_rate = metrics.crawler_success_rate
    success_text = (
        f"{success_rate:.1f}% ({metrics.crawler_successes}/"
        f"{metrics.crawler_finished} tasks)"
        if success_rate is not None
        else "N/A (không có task hoàn tất)"
    )
    return (
        "<b>📊 NewsPulse Intelligence — Daily Report</b>\n"
        f"<i>Ngày {metrics.report_date.strftime('%d/%m/%Y')}</i>\n\n"
        "<b>📈 Dữ liệu đã xử lý</b>\n"
        f"• Bài báo: {metrics.total_articles:,}\n"
        f"• Bài mạng xã hội: {metrics.total_social_posts:,}\n"
        f"• Nguồn hoạt động: {metrics.active_sources:,}\n\n"
        "<b>🩺 Sức khỏe hệ thống</b>\n"
        f"• Alert đã gửi: {metrics.anomaly_alerts:,}\n"
        f"• Crawler thành công: {success_text}\n"
        f"• Độ trễ crawl trung bình: "
        f"{metrics.avg_crawl_latency_minutes:.1f} phút\n\n"
        "<i>Tạo tự động bởi Airflow</i>"
    )
