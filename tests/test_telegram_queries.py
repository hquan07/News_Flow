import asyncio
from datetime import datetime

import pytest

from api.models.telegram import parse_telegram_query
from api.services import telegram_queries
from api.services.telegram_queries import TelegramQueryService


@pytest.fixture(autouse=True)
def run_threaded_queries_inline(monkeypatch):
    async def run_inline(function, *args, **kwargs):
        return function(*args, **kwargs)

    monkeypatch.setattr(telegram_queries.asyncio, "to_thread", run_inline)


def execute(text):
    return asyncio.run(TelegramQueryService().execute(parse_telegram_query(text)))


def test_help_lists_read_only_commands():
    response = execute("/help")

    assert "/alerts" in response.text
    assert "/trend" in response.text
    assert "read-only" in response.text


def test_alerts_formats_recent_spikes(monkeypatch):
    monkeypatch.setattr(
        telegram_queries,
        "get_alerts",
        lambda **_kwargs: [
            {
                "hour_slot": datetime(2026, 10, 2, 9, 0),
                "article_count": 120,
                "z_score": 3.25,
            }
        ],
    )

    response = execute("/alerts 3")

    assert "120 bài" in response.text
    assert "z=3.2" in response.text


def test_trend_parses_range_and_limit(monkeypatch):
    captured = {}

    def trends(**kwargs):
        captured.update(kwargs)
        return [{"keyword": "AI", "count": 42}]

    monkeypatch.setattr(telegram_queries, "get_trending_keywords", trends)

    response = execute("/trend 24h 4")

    assert captured == {"time_range": "today", "limit": 4}
    assert "AI — 42 lần" in response.text


def test_source_requires_name():
    assert "Thiếu tên nguồn" in execute("/source").text


def test_source_aggregates_rows(monkeypatch):
    monkeypatch.setattr(
        telegram_queries,
        "get_source_comparison",
        lambda **_kwargs: [
            {
                "total_articles": 10,
                "avg_word_count": 400,
                "top_category": "tech",
            },
            {
                "total_articles": 5,
                "avg_word_count": 200,
                "top_category": "economy",
            },
        ],
    )

    response = execute("/source vnexpress 7d")

    assert "15" in response.text
    assert "333 từ" in response.text
    assert "economy, tech" in response.text


def test_report_aggregates_overview(monkeypatch):
    monkeypatch.setattr(
        telegram_queries,
        "get_overview",
        lambda **_kwargs: [
            {
                "article_count": 10,
                "source": "vnexpress",
                "category": "tech",
                "avg_crawl_latency": 2.0,
            },
            {
                "article_count": 5,
                "source": "tuoitre",
                "category": "economy",
                "avg_crawl_latency": 5.0,
            },
        ],
    )

    response = execute("/report 30d")

    assert "15" in response.text
    assert "Nguồn hoạt động: 2" in response.text
    assert "3.0 phút" in response.text


def test_status_formats_dependency_health(monkeypatch):
    async def health():
        return {
            "status": "degraded",
            "services": {
                "clickhouse": {"status": "healthy", "latency_ms": 2.5},
                "mongodb": {"status": "unhealthy", "error": "TimeoutError"},
            },
        }

    monkeypatch.setattr(telegram_queries, "dependency_health", health)

    response = execute("/status")

    assert "degraded" in response.text
    assert "clickhouse: healthy — 2.5 ms" in response.text
    assert "mongodb: unhealthy" in response.text


def test_unknown_command_is_read_only_help_response():
    response = execute("/delete_everything")

    assert "chưa được hỗ trợ" in response.text
