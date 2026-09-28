from api.services import analytics


def test_viral_alert_marks_live_demo_post_as_synthetic(monkeypatch):
    monkeypatch.setattr(
        analytics,
        "_query",
        lambda *_args, **_kwargs: [
            {
                "post_id": "live_post_demo-123",
                "source": "reddit_vn",
                "title": "Chủ đề đang hot trên reddit_vn",
                "interactions": 148,
                "sentiment_label": "neutral",
                "publish_time": None,
            }
        ],
    )

    alerts = analytics.get_viral_post_alerts()

    assert alerts[0]["title"] == ""
    assert alerts[0]["data_quality"] == {
        "title_available": False,
        "synthetic": True,
    }


def test_viral_alert_keeps_production_post_unlabelled(monkeypatch):
    monkeypatch.setattr(
        analytics,
        "_query",
        lambda *_args, **_kwargs: [
            {
                "post_id": "reddit_123",
                "source": "reddit_vn",
                "title": "A real discussion title",
                "interactions": 70,
                "sentiment_label": "positive",
                "publish_time": None,
            }
        ],
    )

    alerts = analytics.get_viral_post_alerts()

    assert alerts[0]["data_quality"] == {
        "title_available": True,
        "synthetic": False,
    }


def test_stream_supports_canonical_path_without_trailing_slash():
    from api.main import app

    stream_paths = {
        route.path
        for route in app.routes
        if "GET" in getattr(route, "methods", set()) and "stream" in route.path
    }

    assert "/api/v1/stream" in stream_paths
    assert "/api/v1/stream/" in stream_paths
