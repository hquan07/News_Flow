from datetime import datetime

from api.services import analytics


def test_sentiment_timeline_uses_article_publish_time_and_filters(monkeypatch):
    captured = {}

    def fake_query(sql, params=None):
        captured["sql"] = sql
        captured["params"] = params
        return [
            {
                "time": datetime(2026, 9, 28),
                "sentiment_label": "positive",
                "count": 3,
            }
        ]

    monkeypatch.setattr(analytics, "_query", fake_query)
    result = analytics.get_sentiment_timeline(
        time_range="7d", source="vnexpress", category="tech"
    )

    assert "toStartOfDay(a.publish_time)" in captured["sql"]
    assert "INNER JOIN newspulse.raw_articles" in captured["sql"]
    assert captured["params"] == {"source": "vnexpress", "category": "tech"}
    assert result[0]["Positive"] == 3


def test_sentiment_by_source_uses_linked_article_source(monkeypatch):
    captured = {}

    def fake_query(sql, params=None):
        captured["sql"] = sql
        return [
            {"source": "tuoitre", "sentiment": "negative", "count": 4}
        ]

    monkeypatch.setattr(analytics, "_query", fake_query)
    result = analytics.get_sentiment_by_source(time_range="all")

    assert "a.source AS source" in captured["sql"]
    assert result == [
        {"source": "tuoitre", "Positive": 0, "Negative": 4, "Neutral": 0}
    ]


def test_sentiment_coverage_reports_orphans(monkeypatch):
    monkeypatch.setattr(
        analytics, "_query_one", lambda _sql: {"total": 5000, "linked": 1250}
    )

    assert analytics.get_sentiment_coverage() == {
        "total": 5000,
        "linked": 1250,
        "unlinked": 3750,
        "coverage_pct": 25.0,
    }
