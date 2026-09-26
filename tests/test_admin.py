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
