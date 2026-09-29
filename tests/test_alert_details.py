from datetime import datetime, timedelta

import pytest
from httpx import AsyncClient

from api.services import analytics


def test_crisis_detail_combines_distribution_and_contributors(monkeypatch):
    monkeypatch.setattr(
        analytics,
        "get_social_crisis_alerts",
        lambda **_kwargs: [
            {
                "source": "reddit_vn",
                "total_posts": 20,
                "negative_posts": 12,
                "negative_pct": 60.0,
                "negative_pct_threshold": 30.0,
                "min_posts_threshold": 10,
                "alert_reason": "Threshold exceeded.",
            }
        ],
    )
    query_results = iter([
        [{"label": "negative", "count": 12}, {"label": "neutral", "count": 8}],
        [
            {
                "post_id": "live_post_1",
                "source": "reddit_vn",
                "title": "Chủ đề đang hot trên reddit_vn",
                "interactions": 99,
                "sentiment_label": "negative",
                "publish_time": None,
            }
        ],
    ])
    monkeypatch.setattr(analytics, "_query", lambda *_args, **_kwargs: next(query_results))

    detail = analytics.get_social_crisis_detail("reddit_vn")

    assert detail["sentiment_distribution"][0] == {"label": "negative", "count": 12}
    assert detail["top_negative_posts"][0]["data_quality"]["synthetic"] is True
    assert detail["top_negative_posts"][0]["title"] == ""


def test_volume_spike_detail_returns_exact_hour_articles(monkeypatch):
    hour_slot = datetime(2026, 9, 28, 10, 0)
    calls = []
    query_results = iter([
        [{"hour_slot": hour_slot, "article_count": 40, "avg_count": 10.0, "std_count": 5.0, "z_score": 6.0}],
        [{"article_id": "hash-1", "title": "Breaking news"}],
    ])

    def fake_query(sql, params=None):
        calls.append((sql, params))
        return next(query_results)

    monkeypatch.setattr(analytics, "_query", fake_query)

    detail = analytics.get_volume_spike_detail(hour_slot, threshold=2.0)

    assert detail["window_end"] == hour_slot + timedelta(hours=1)
    assert detail["is_active"] is True
    assert detail["articles"][0]["article_id"] == "hash-1"
    assert calls[1][1]["window_end"] == hour_slot + timedelta(hours=1)


@pytest.mark.asyncio
async def test_crisis_detail_endpoint(async_client: AsyncClient, monkeypatch):
    async def thresholds():
        return {
            "crisis_negative_pct": 30.0,
            "crisis_min_posts": 10,
            "viral_interactions": 50,
        }

    monkeypatch.setattr("api.routers.alerts.get_alert_thresholds", thresholds)
    monkeypatch.setattr(
        "api.routers.alerts.get_social_crisis_detail",
        lambda *_args, **_kwargs: {
            "source": "reddit_vn",
            "total_posts": 20,
            "negative_posts": 12,
            "negative_pct": 60.0,
            "negative_pct_threshold": 30.0,
            "min_posts_threshold": 10,
            "alert_reason": "Threshold exceeded.",
            "sentiment_distribution": [{"label": "negative", "count": 12}],
            "top_negative_posts": [],
        },
    )

    response = await async_client.get("/api/v1/alerts/social/crisis/reddit_vn")

    assert response.status_code == 200
    assert response.json()["sentiment_distribution"][0]["count"] == 12


@pytest.mark.asyncio
async def test_volume_detail_endpoint(async_client: AsyncClient, monkeypatch):
    hour_slot = datetime(2026, 9, 28, 10, 0)
    monkeypatch.setattr(
        "api.routers.alerts.get_volume_spike_detail",
        lambda *_args, **_kwargs: {
            "hour_slot": hour_slot,
            "window_end": hour_slot + timedelta(hours=1),
            "article_count": 40,
            "avg_count": 10.0,
            "std_count": 5.0,
            "z_score": 6.0,
            "threshold": 2.0,
            "is_active": True,
            "alert_reason": "Threshold exceeded.",
            "articles": [],
        },
    )

    response = await async_client.get(
        "/api/v1/alerts/volume/2026-09-28T10:00:00?threshold=2"
    )

    assert response.status_code == 200
    assert response.json()["z_score"] == 6.0
