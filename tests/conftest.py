import os
from datetime import datetime, timezone

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

os.environ.setdefault("JWT_SECRET_KEY", "test-only-secret-key-with-at-least-32-chars")

from api.main import app
from api.middleware import rate_limiter
from api.security import create_access_token


ARTICLES = [
    {
        "article_id": "hash_test_1",
        "title": "Test AI Article",
        "url": "https://example.com/test-1",
        "source": "vnexpress",
        "category": "tech",
        "publish_date": datetime(2026, 9, 26, tzinfo=timezone.utc),
        "publish_hour": 10,
        "author": "Test Author",
        "word_count": 500,
        "keyword_count": 2,
        "crawl_latency_minutes": 2.5,
        "sentiment_score": 0.5,
    },
    {
        "article_id": "hash_test_2",
        "title": "Test Sports Article",
        "url": "https://example.com/test-2",
        "source": "tuoitre",
        "category": "sports",
        "publish_date": datetime(2026, 9, 26, tzinfo=timezone.utc),
        "publish_hour": 14,
        "author": "",
        "word_count": 300,
        "keyword_count": 1,
        "crawl_latency_minutes": 1.8,
        "sentiment_score": 0.0,
    },
]


@pytest_asyncio.fixture
async def async_client():
    transport = ASGITransport(app=app)
    token = create_access_token({"sub": "test-admin", "role": "admin"})
    async with AsyncClient(
        transport=transport,
        base_url="http://test",
        headers={"Authorization": f"Bearer {token}"},
    ) as client:
        yield client


@pytest.fixture(autouse=True)
def mock_data_services(monkeypatch):
    rate_limiter.reset()
    def fake_articles(
        page=1,
        page_size=20,
        q=None,
        author=None,
        source=None,
        category=None,
        date_from=None,
        date_to=None,
        entity=None,
        keyword=None,
        sentiment=None,
        **_kwargs,
    ):
        rows = ARTICLES
        if q:
            rows = [row for row in rows if q.lower() in row["title"].lower()]
        if author:
            rows = [row for row in rows if row["author"].casefold() == author.casefold()]
        if source:
            rows = [row for row in rows if row["source"] == source]
        if category:
            rows = [row for row in rows if row["category"] == category]
        if date_from:
            rows = [row for row in rows if row["publish_date"].date() >= date_from]
        if date_to:
            rows = [row for row in rows if row["publish_date"].date() <= date_to]
        if sentiment:
            rows = [row for row in rows if (
                "positive" if row["sentiment_score"] > 0 else
                "negative" if row["sentiment_score"] < 0 else "neutral"
            ) == sentiment]
        start = (page - 1) * page_size
        data = rows[start:start + page_size]
        return {
            "total": len(rows),
            "page": page,
            "page_size": page_size,
            "total_pages": (len(rows) + page_size - 1) // page_size,
            "data": data,
        }

    def fake_article_detail(article_id):
        row = next((item for item in ARTICLES if item["article_id"] == article_id), None)
        if row is None:
            return None
        return {**row, "keywords": ["AI", "machine learning"], "entities": []}

    monkeypatch.setattr("api.routers.articles.get_articles", fake_articles)
    monkeypatch.setattr("api.routers.articles.get_article_detail", fake_article_detail)
    monkeypatch.setattr(
        "api.routers.overview.get_overview",
        lambda **_kwargs: [
            {
                "date": "2026-09-26",
                "source": "vnexpress",
                "category": "tech",
                "article_count": 2,
                "avg_word_count": 400,
                "avg_crawl_latency": 2.0,
            }
        ],
    )
    monkeypatch.setattr(
        "api.routers.overview.get_hourly_distribution",
        lambda **_kwargs: [{"hour": 10, "source": "vnexpress", "total_count": 2}],
    )
    monkeypatch.setattr(
        "api.routers.overview.get_sentiment_distribution",
        lambda **_kwargs: [{"sentiment_label": "Positive", "count": 2}],
    )
    monkeypatch.setattr(
        "api.routers.trending.get_trending_keywords",
        lambda limit=20, **_kwargs: [{"keyword": "AI", "count": 2}][:limit],
    )
    monkeypatch.setattr(
        "api.routers.entities.get_entity_stats",
        lambda entity_type=None, limit=20, **_kwargs: [
            {
                "entity_name": "Việt Nam",
                "entity_type": entity_type or "LOC",
                "article_count": 2,
                "mention_count": 3,
            }
        ][:limit],
    )
