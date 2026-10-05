import pytest
from httpx import AsyncClient
from api.services import health


@pytest.mark.asyncio
async def test_liveness_includes_request_id(async_client: AsyncClient):
    response = await async_client.get(
        "/health",
        headers={"X-Request-ID": "test-request-123"},
    )
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"
    assert response.headers["X-Request-ID"] == "test-request-123"

    live_response = await async_client.get("/health/live")
    assert live_response.status_code == 200
    assert live_response.json()["status"] == "healthy"


@pytest.mark.asyncio
async def test_clickhouse_healthcheck_does_not_close_shared_client(monkeypatch):
    class SharedClient:
        closed = False

        def command(self, sql):
            assert sql == "SELECT 1"

        def close(self):
            self.closed = True

    client = SharedClient()
    monkeypatch.setattr(health, "get_ch_client", lambda: client)

    result = await health._check_clickhouse()

    assert result["status"] == "healthy"
    assert client.closed is False


@pytest.mark.asyncio
async def test_readiness_returns_dependency_status(async_client: AsyncClient, monkeypatch):
    async def healthy_dependencies():
        return {
            "status": "healthy",
            "services": {
                "clickhouse": {"status": "healthy"},
                "mongodb": {"status": "healthy"},
            },
        }

    monkeypatch.setattr("api.main.dependency_health", healthy_dependencies)
    response = await async_client.get("/health/ready")
    assert response.status_code == 200
    assert response.json()["services"]["clickhouse"]["status"] == "healthy"


@pytest.mark.asyncio
async def test_readiness_returns_503_when_dependency_is_down(async_client: AsyncClient, monkeypatch):
    async def degraded_dependencies():
        return {
            "status": "degraded",
            "services": {
                "clickhouse": {"status": "unhealthy", "error": "TimeoutError"},
                "mongodb": {"status": "healthy"},
            },
        }

    monkeypatch.setattr("api.main.dependency_health", degraded_dependencies)
    response = await async_client.get("/health/ready")
    assert response.status_code == 503
    assert response.json()["status"] == "degraded"


@pytest.mark.asyncio
async def test_prometheus_metrics_use_route_labels_without_scrape_self_count(async_client: AsyncClient):
    await async_client.get("/health/live")
    first = await async_client.get("/metrics")
    second = await async_client.get("/metrics")

    assert first.status_code == 200
    assert 'newspulse_http_requests_total{method="GET",route="/health/live",status="200"}' in first.text
    assert "newspulse_http_request_duration_seconds_bucket" in first.text
    assert 'route="/metrics"' not in second.text
