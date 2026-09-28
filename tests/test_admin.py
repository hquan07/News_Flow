from datetime import datetime, timezone

import pytest
from httpx import AsyncClient

from api.security import create_access_token


@pytest.mark.asyncio
async def test_admin_metrics_require_auth(async_client: AsyncClient):
    response = await async_client.get("/api/v1/admin/metrics/latency")
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
