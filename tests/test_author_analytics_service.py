from api.services import author_analytics


def test_get_author_analytics_builds_coverage_and_rankings(monkeypatch):
    calls = []
    author_rows = [
        {
            "author": "Test Author",
            "source": "vnexpress",
            "article_count": 2,
            "top_category": "tech",
            "analyzed_count": 2,
            "avg_sentiment": 0.2,
        }
    ]
    source_rows = [
        {
            "source": "vnexpress",
            "total_articles": 3,
            "authored_articles": 2,
            "author_count": 1,
        }
    ]
    trend_rows = [
        {
            "period": "2026-09-26",
            "author": "Test Author",
            "source": "vnexpress",
            "article_count": 2,
        }
    ]
    category_rows = [
        {
            "author": "Test Author",
            "source": "vnexpress",
            "category": "tech",
            "article_count": 2,
        }
    ]

    def fake_execute(operation):
        class FakeResult:
            def __init__(self, rows):
                self._rows = rows

            def named_results(self):
                return iter(self._rows)

        class FakeClient:
            def query(self, sql, parameters):
                calls.append((sql, parameters))
                rows_by_call = {
                    1: [{"total_articles": 3, "authored_articles": 2, "total_authors": 1}],
                    2: author_rows,
                    3: source_rows,
                    4: trend_rows,
                    5: category_rows,
                }
                rows = rows_by_call[len(calls)]
                return FakeResult(rows)

        return operation(FakeClient())

    monkeypatch.setattr(author_analytics, "execute_clickhouse", fake_execute)

    result = author_analytics.get_author_analytics(
        time_range="30d",
        source="vnexpress",
        limit=20,
    )

    assert result["summary"] == {
        "total_authors": 1,
        "total_articles": 3,
        "authored_articles": 2,
        "unattributed_articles": 1,
        "coverage_pct": 66.7,
    }
    assert result["authors"] == author_rows
    assert result["source_breakdown"][0]["missing_articles"] == 1
    assert result["source_breakdown"][0]["coverage_pct"] == 66.7
    assert result["publication_trend"] == trend_rows
    assert result["category_breakdown"] == category_rows
    assert len(calls) == 5
    assert "publish_time >= now() - INTERVAL 30 DAY" in calls[0][0]
    assert calls[0][1]["source"] == "vnexpress"
    assert calls[1][1]["limit"] == 20
    assert "toDate(publish_time)" in calls[3][0]
    assert calls[3][1]["author_0"] == "test author"


def test_get_author_analytics_handles_empty_dataset(monkeypatch):
    def fake_execute(operation):
        class FakeResult:
            def named_results(self):
                return iter([])

        class FakeClient:
            def query(self, _sql, parameters):
                assert parameters["limit"] == 50
                return FakeResult()

        return operation(FakeClient())

    monkeypatch.setattr(author_analytics, "execute_clickhouse", fake_execute)

    result = author_analytics.get_author_analytics()

    assert result["summary"]["coverage_pct"] == 0.0
    assert result["summary"]["unattributed_articles"] == 0
    assert result["authors"] == []
    assert result["source_breakdown"] == []
    assert result["publication_trend"] == []
    assert result["category_breakdown"] == []
