from datetime import datetime, timezone

from api.routers import social


def test_content_performance_aggregates_and_applies_source(monkeypatch):
    calls = []
    responses = iter([
        [{
            "total_posts": 12,
            "total_interactions": 420,
            "avg_interactions_per_post": 35.0,
            "high_performing_posts": 3,
        }],
        [{
            "source": "reddit_vn",
            "post_count": 12,
            "total_likes": 300,
            "total_replies": 120,
            "total_interactions": 420,
            "avg_interactions_per_post": 35.0,
        }],
        [{
            "post_id": "post-1",
            "source": "reddit_vn",
            "interactions": 80,
        }, {
            "post_id": "post-1",
            "source": "reddit_vn",
            "interactions": 80,
        }],
    ])

    def fake_query(sql, params=None):
        calls.append((sql, params or {}))
        return next(responses)

    monkeypatch.setattr(social, "_query", fake_query)
    payload = social.social_content_performance("all", "reddit_vn", 10)

    assert payload["summary"]["total_interactions"] == 420
    assert payload["top_posts"][0]["post_id"] == "post-1"
    assert len(payload["top_posts"]) == 1
    assert all(call[1].get("source") == "reddit_vn" for call in calls)
    assert calls[-1][1]["limit"] == 10
    assert "source = {source:String}" in calls[0][0]


def test_audience_reports_peak_hour_and_frequency(monkeypatch):
    responses = iter([
        [{"total_posts": 20, "unique_contributors": 5, "active_platforms": 2}],
        [
            {"hour": 8, "post_count": 4, "active_contributors": 3, "interactions": 30},
            {"hour": 20, "post_count": 9, "active_contributors": 5, "interactions": 90},
        ],
        [{"segment": "Core", "contributors": 2}],
        [{"source": "youtube", "post_count": 10, "contributors": 4, "interactions": 75}],
    ])
    monkeypatch.setattr(social, "_query", lambda *_args, **_kwargs: next(responses))

    payload = social.social_audience("7d", None)

    assert payload["summary"] == {
        "total_posts": 20,
        "unique_contributors": 5,
        "active_platforms": 2,
        "avg_posts_per_contributor": 4.0,
        "peak_hour": 20,
    }
    assert "not passive viewers" in payload["methodology"]


def test_topics_summarizes_ranked_results(monkeypatch):
    responses = iter([
        [
            {"hashtag": "#ai", "mentions": 7, "interactions": 100},
            {"hashtag": "#news", "mentions": 3, "interactions": 40},
        ],
        [
            {"topic": "AI launch", "source": "youtube", "post_count": 2, "interactions": 75, "sentiment_score": 0.4},
        ],
    ])
    monkeypatch.setattr(social, "_query", lambda *_args, **_kwargs: next(responses))

    payload = social.social_topics("30d", None, 20)

    assert payload["summary"] == {
        "unique_hashtags": 2,
        "hashtag_mentions": 10,
        "tracked_topics": 1,
        "topic_interactions": 75,
    }


def test_alert_signals_apply_thresholds(monkeypatch):
    responses = iter([
        [
            {"source": "reddit_vn", "total_posts": 20, "negative_posts": 9, "negative_pct": 45.0, "interactions": 300},
            {"source": "youtube", "total_posts": 5, "negative_posts": 2, "negative_pct": 40.0, "interactions": 60},
        ],
        [{
            "post_id": "viral-1",
            "source": "reddit_vn",
            "interactions": 120,
            "publish_time": datetime(2026, 10, 7, tzinfo=timezone.utc),
        }, {
            "post_id": "viral-1",
            "source": "reddit_vn",
            "interactions": 120,
            "publish_time": datetime(2026, 10, 7, tzinfo=timezone.utc),
        }],
    ])
    monkeypatch.setattr(social, "_query", lambda *_args, **_kwargs: next(responses))

    payload = social.social_alert_signals(None, 30.0, 10, 50)

    assert payload["source_risks"][0]["active"] is True
    assert payload["source_risks"][1]["active"] is False
    assert payload["summary"] == {
        "active_alerts": 2,
        "crisis_sources": 1,
        "viral_posts": 1,
        "negative_posts": 11,
    }
    assert payload["window"] == "Last 24 hours"
