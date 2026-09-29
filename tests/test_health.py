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
