import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_liveness_includes_request_id(async_client: AsyncClient):
    response = await async_client.get(
        "/health",
        headers={"X-Request-ID": "test-request-123"},
    )
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"
    assert response.headers["X-Request-ID"] == "test-request-123"


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
