from datetime import date, datetime, timezone

from infrastructure.monitoring.daily_report import (
    DailyMetrics,
    count_sent_alerts,
    fetch_clickhouse_daily_metrics,
    format_daily_report,
)


class QueryResult:
    def __init__(self, rows):
        self.rows = rows

    def named_results(self):
        return iter(self.rows)


class FakeClickHouse:
    def __init__(self):
        self.calls = []

    def query(self, sql, parameters):
        self.calls.append((sql, parameters))
        if "raw_articles" in sql:
            return QueryResult(
                [
                    {
                        "total_articles": 1250,
                        "active_sources": 8,
                        "avg_crawl_latency": 2.4,
                    }
                ]
            )
        return QueryResult([{"total_social_posts": 320}])


class FakeCollection:
    def __init__(self):
        self.query = None

    def count_documents(self, query):
        self.query = query
        return 6


def test_fetch_clickhouse_daily_metrics_uses_bounded_window():
    client = FakeClickHouse()
    start_at = datetime(2026, 10, 1, tzinfo=timezone.utc)
    end_at = datetime(2026, 10, 2, tzinfo=timezone.utc)

    metrics = fetch_clickhouse_daily_metrics(client, start_at, end_at)

    assert metrics == {
        "total_articles": 1250,
        "active_sources": 8,
        "avg_crawl_latency_minutes": 2.4,
        "total_social_posts": 320,
    }
    assert len(client.calls) == 2
    assert all(
        call[1] == {"start_at": start_at, "end_at": end_at}
        for call in client.calls
    )


def test_count_sent_alerts_uses_delivery_time_window():
    collection = FakeCollection()
    start_at = datetime(2026, 10, 1, tzinfo=timezone.utc)
    end_at = datetime(2026, 10, 2, tzinfo=timezone.utc)

    assert count_sent_alerts(collection, start_at, end_at) == 6
    assert collection.query == {
        "status": "sent",
        "sent_at": {"$gte": start_at, "$lt": end_at},
    }


def test_format_daily_report_uses_real_metric_units():
    metrics = DailyMetrics(
        report_date=date(2026, 10, 1),
        total_articles=1250,
        total_social_posts=320,
        active_sources=8,
        anomaly_alerts=6,
        crawler_successes=45,
        crawler_finished=48,
        avg_crawl_latency_minutes=2.4,
    )

    report = format_daily_report(metrics)

    assert "1,250" in report
    assert "93.8% (45/48 tasks)" in report
    assert "2.4 phút" in report
    assert "01/10/2026" in report


def test_format_daily_report_handles_no_finished_crawlers():
    metrics = DailyMetrics(
        report_date=date(2026, 10, 1),
        total_articles=0,
        total_social_posts=0,
        active_sources=0,
        anomaly_alerts=0,
        crawler_successes=0,
        crawler_finished=0,
        avg_crawl_latency_minutes=0,
    )

    assert "N/A" in format_daily_report(metrics)
