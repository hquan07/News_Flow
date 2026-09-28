from datetime import datetime

import pytest
from httpx import AsyncClient

from api.security import create_access_token
from api.services.alert_metrics import alert_metrics


def _admin_headers():
    token = create_access_token(
        {"sub": "metrics-admin", "email": "admin@example.com", "role": "admin"}
    )
    return {"Authorization": f"Bearer {token}"}


def test_alert_metrics_records_outcomes_and_latency():
    alert_metrics.reset()
    alert_metrics.observe("viral_detail", "success", 0.012)
    alert_metrics.observe("viral_detail", "not_found", 0.008)
    alert_metrics.observe("state_update", "error", 0.004)

    snapshot = alert_metrics.snapshot()

    assert snapshot["scope"] == "process-local"
    assert snapshot["totals"] == {
        "requests": 3,
        "successes": 1,
        "not_found": 1,
        "errors": 1,
    }
    assert snapshot["operations"]["viral_detail"]["average_latency_ms"] == 10.0
    assert snapshot["operations"]["viral_detail"]["max_latency_ms"] == 12.0


@pytest.mark.asyncio
async def test_alert_metrics_endpoint_requires_admin(async_client: AsyncClient):
    response = await async_client.get("/api/v1/alerts/metrics")

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_alert_metrics_endpoint_returns_snapshot(async_client: AsyncClient):
    alert_metrics.reset()
    alert_metrics.observe("interaction_trend", "success", 0.005)

    response = await async_client.get(
        "/api/v1/alerts/metrics",
        headers=_admin_headers(),
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["scope"] == "process-local"
    assert payload["totals"]["requests"] == 1
    assert payload["operations"]["interaction_trend"]["successes"] == 1


@pytest.mark.asyncio
async def test_social_alert_snapshot_includes_generation_time(
    async_client: AsyncClient,
    monkeypatch,
):
    monkeypatch.setattr("api.routers.alerts.get_social_crisis_alerts", lambda **_kwargs: [])
    monkeypatch.setattr("api.routers.alerts.get_viral_post_alerts", lambda **_kwargs: [])

    response = await async_client.get("/api/v1/alerts/social")

    assert response.status_code == 200
    payload = response.json()
    assert payload["crisis_alerts"] == []
    assert payload["viral_alerts"] == []
    assert datetime.fromisoformat(payload["generated_at"]).tzinfo is not None
