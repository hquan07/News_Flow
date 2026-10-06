import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_author_analytics_returns_ranked_authors(
    async_client: AsyncClient,
    monkeypatch,
):
    captured = {}

    def fake_author_analytics(*, time_range, source, limit):
        captured.update(
            time_range=time_range,
            source=source,
            limit=limit,
        )
        return {
            "summary": {
                "total_authors": 1,
                "total_articles": 3,
                "authored_articles": 2,
                "unattributed_articles": 1,
                "coverage_pct": 66.7,
            },
            "authors": [
                {
                    "author": "Test Author",
                    "source": "vnexpress",
                    "article_count": 2,
                    "top_category": "tech",
                    "first_published_at": "2026-09-20T08:00:00",
                    "last_published_at": "2026-09-26T10:00:00",
                    "positive_count": 1,
                    "neutral_count": 1,
                    "negative_count": 0,
                    "analyzed_count": 2,
                    "avg_sentiment": 0.25,
                }
            ],
            "time_range": time_range,
            "source": source,
        }

    monkeypatch.setattr(
        "api.routers.authors.get_author_analytics",
        fake_author_analytics,
    )

    response = await async_client.get(
        "/api/v1/authors",
        params={"time_range": "30d", "source": "vnexpress", "limit": 20},
    )

    assert response.status_code == 200
    assert captured == {
        "time_range": "30d",
        "source": "vnexpress",
        "limit": 20,
    }
    payload = response.json()
    assert payload["summary"]["coverage_pct"] == 66.7
    assert payload["authors"][0]["author"] == "Test Author"


@pytest.mark.asyncio
async def test_author_analytics_rejects_invalid_time_range(
    async_client: AsyncClient,
):
    response = await async_client.get(
        "/api/v1/authors",
        params={"time_range": "90d"},
    )

    assert response.status_code == 422
