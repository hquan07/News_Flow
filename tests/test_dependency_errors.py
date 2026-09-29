import pytest
from httpx import AsyncClient

from api.exceptions import DependencyUnavailableError


@pytest.mark.asyncio
async def test_dependency_failure_returns_structured_503(
    async_client: AsyncClient,
    monkeypatch,
):
    def unavailable(**_kwargs):
        raise DependencyUnavailableError("clickhouse")

    monkeypatch.setattr("api.routers.overview.get_overview", unavailable)

    response = await async_client.get(
        "/api/v1/overview",
        headers={"X-Request-ID": "dependency-test-123"},
    )

    assert response.status_code == 503
    assert response.json() == {
        "error": {
            "code": "DEPENDENCY_UNAVAILABLE",
            "message": "Required data service is temporarily unavailable",
            "dependency": "clickhouse",
            "request_id": "dependency-test-123",
        }
    }
