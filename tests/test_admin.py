from datetime import datetime, timezone

import pytest
from httpx import AsyncClient

from api.security import create_access_token
from api.routers import admin


@pytest.mark.asyncio
async def test_admin_metrics_require_auth(async_client: AsyncClient):
    response = await async_client.get(
        "/api/v1/admin/metrics/latency",
        headers={"Authorization": ""},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_admin_metrics_reject_non_admin(async_client: AsyncClient):
    token = create_access_token({"sub": "user-1", "role": "user"})
    response = await async_client.get(
        "/api/v1/admin/metrics/latency",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_operations_metrics_report_current_article_coverage(
    async_client: AsyncClient, monkeypatch
):
    now = datetime.now(timezone.utc).replace(second=0, microsecond=0)
    monkeypatch.setattr(
        "api.routers.admin._query_one",
        lambda _query: {
            "total_articles": 200,
            "articles_last_24h": 25,
            "latest_loaded_at": now,
            "nlp_linked_articles": 50,
        },
    )
    token = create_access_token({"sub": "admin-1", "role": "admin"})

    response = await async_client.get(
        "/api/v1/admin/metrics/operations",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["articles_last_24h"] == 25
    assert data["nlp_linked_articles"] == 50
    assert data["nlp_coverage_pct"] == 25.0
    assert data["freshness_minutes"] is not None


def test_latency_metric_uses_recent_weighted_samples(monkeypatch):
    captured = {}

    def fake_query(query):
        captured["query"] = query
        return [
            {"source": "vnexpress", "latency_sum": 20, "latency_count": 4},
            {"source": "tuoitre", "latency_sum": 10, "latency_count": 1},
        ]

    monkeypatch.setattr(admin, "_query", fake_query)

    result = admin.get_crawl_latency(user={})

    assert result["overall_average"] == 6.0
    assert result["sample_count"] == 5
    assert result["window_minutes"] == 60
    assert "publish_time >= now() - INTERVAL 60 MINUTE" in captured["query"]
