from datetime import datetime, timezone

from api.services import advanced_analytics


def test_forecast_series_follows_trend_and_returns_interval():
    points = advanced_analytics.forecast_series([10, 12, 14, 16, 18], 3)
    assert [point["value"] for point in points] == [20.0, 22.0, 24.0]
    assert all(point["lower"] <= point["value"] <= point["upper"] for point in points)


def test_propagation_identifies_origin_peak_and_delays(monkeypatch):
    start = datetime(2026, 10, 1, 8, tzinfo=timezone.utc)
    monkeypatch.setattr(advanced_analytics, "_query", lambda *_args, **_kwargs: [
        {"bucket": start, "source": "vnexpress", "article_count": 1},
        {"bucket": start.replace(hour=9), "source": "tuoitre", "article_count": 4},
        {"bucket": start.replace(hour=10), "source": "thanhnien", "article_count": 2},
    ])
    result = advanced_analytics.propagation("VinFast")
    assert result["origin"]["source"] == "vnexpress"
    assert result["peak"]["source"] == "tuoitre"
    assert result["source_delays_minutes"][-1] == {"source": "thanhnien", "delay_minutes": 120}


def test_source_divergence_is_labeled_as_title_vocabulary_not_bias(monkeypatch):
    monkeypatch.setattr(advanced_analytics, "event_detail", lambda *_args, **_kwargs: {
        "title": "AI event", "articles": [
            {"article_id": "a", "title": "AI giúp tăng trưởng kinh tế", "source": "one"},
            {"article_id": "b", "title": "Rủi ro AI với việc làm", "source": "two"},
        ],
    })
    monkeypatch.setattr(advanced_analytics, "_query", lambda *_args, **_kwargs: [
        {"source": "one", "avg_sentiment": 0.5}, {"source": "two", "avg_sentiment": -0.3},
    ])
    result = advanced_analytics.source_divergence("event")
    assert result["comparisons"][0]["sentiment_gap"] == 0.8
    assert "does not determine editorial bias" in result["note"]


def test_nlp_explanation_returns_ranked_evidence(monkeypatch):
    responses = iter([
        [{"article_id": "a", "title": "AI tại Việt Nam", "source": "one", "content": "Nghiên cứu AI đang phát triển nhanh tại Việt Nam.", "sentiment_score": 0.7, "sentiment_label": "positive"}],
        [{"keyword": "AI", "score": 0.95}],
        [{"name": "Việt Nam", "type": "LOC", "mentions": 1}],
    ])
    monkeypatch.setattr(advanced_analytics, "_query", lambda *_args, **_kwargs: next(responses))
    result = advanced_analytics.nlp_explanation("a")
    assert result["keywords"][0]["keyword"] == "AI"
    assert result["entities"][0]["name"] == "Việt Nam"
    assert result["evidence"]
