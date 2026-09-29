from datetime import datetime, timezone

import pytest
from httpx import AsyncClient

from api.security import create_access_token
from api.services.alert_metrics import alert_metrics
from api.services import alert_metrics as alert_metrics_module


def _admin_headers():
    token = create_access_token(
        {"sub": "metrics-admin", "email": "admin@example.com", "role": "admin"}
    )
    return {"Authorization": f"Bearer {token}"}


class _MetricsCursor:
    def __init__(self, documents):
        self.documents = documents

    async def to_list(self, length):
        return self.documents[:length]


class _MetricsCollection:
    def __init__(self):
        now = datetime.now(timezone.utc)
        self.documents = {
            "other-worker": {
                "started_at": now,
                "last_seen_at": now,
                "operations": {
                    "viral_detail": {
                        "requests": 1,
                        "successes": 0,
                        "not_found": 1,
                        "errors": 0,
                        "total_latency_ms": 8.0,
                        "max_latency_ms": 8.0,
                    }
                },
            }
        }

    async def update_one(self, query, update, upsert=False):
        assert upsert is True
        self.documents[query["_id"]] = update["$set"]

    def find(self, _query, _projection=None):
        return _MetricsCursor(list(self.documents.values()))


class _MetricsDb:
    def __init__(self):
        self.alert_metric_workers = _MetricsCollection()


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
async def test_alert_metrics_aggregate_active_workers(monkeypatch):
    database = _MetricsDb()
    monkeypatch.setattr(alert_metrics_module, "get_mongo_db", lambda: database)
    alert_metrics.reset()
    alert_metrics.observe("viral_detail", "success", 0.012)

    snapshot = await alert_metrics.shared_snapshot()

    assert snapshot["scope"] == "shared-mongodb"
    assert snapshot["workers"] == 2
    assert snapshot["totals"]["requests"] == 2
    assert snapshot["operations"]["viral_detail"]["average_latency_ms"] == 10.0


@pytest.mark.asyncio
async def test_alert_metrics_endpoint_requires_admin(async_client: AsyncClient):
    response = await async_client.get("/api/v1/alerts/metrics")

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_alert_metrics_endpoint_returns_snapshot(
    async_client: AsyncClient,
    monkeypatch,
):
    alert_metrics.reset()
    alert_metrics.observe("interaction_trend", "success", 0.005)

    local_snapshot = alert_metrics.snapshot()
    local_snapshot["scope"] = "shared-mongodb"

    async def fake_shared_snapshot():
        return local_snapshot

    monkeypatch.setattr(alert_metrics, "shared_snapshot", fake_shared_snapshot)
    response = await async_client.get(
        "/api/v1/alerts/metrics",
        headers=_admin_headers(),
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["scope"] == "shared-mongodb"
    assert payload["totals"]["requests"] == 1
    assert payload["operations"]["interaction_trend"]["successes"] == 1


@pytest.mark.asyncio
async def test_social_alert_snapshot_includes_generation_time(
    async_client: AsyncClient,
    monkeypatch,
):
    async def thresholds():
        return {
            "crisis_negative_pct": 30.0,
            "crisis_min_posts": 10,
            "viral_interactions": 50,
        }

    monkeypatch.setattr("api.routers.alerts.get_alert_thresholds", thresholds)
    monkeypatch.setattr("api.routers.alerts.get_social_crisis_alerts", lambda *_args: [])
    monkeypatch.setattr("api.routers.alerts.get_viral_post_alerts", lambda *_args: [])

    response = await async_client.get("/api/v1/alerts/social")

    assert response.status_code == 200
    payload = response.json()
    assert payload["crisis_alerts"] == []
    assert payload["viral_alerts"] == []
    assert datetime.fromisoformat(payload["generated_at"]).tzinfo is not None
