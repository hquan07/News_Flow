import pytest
from httpx import AsyncClient

from api.security import create_access_token, permissions_for_role


def _headers(role: str):
    token = create_access_token({"sub": f"{role}-1", "role": role})
    return {"Authorization": f"Bearer {token}"}


def test_role_permissions_are_distinct():
    assert "reports.export_full" not in permissions_for_role("user")
    assert "reports.export_full" in permissions_for_role("analyst")
    assert "crawler.run" in permissions_for_role("operator")
    assert "users.manage" not in permissions_for_role("operator")
    assert "users.manage" in permissions_for_role("admin")


@pytest.mark.asyncio
async def test_dashboard_requires_login(async_client: AsyncClient):
    response = await async_client.get(
        "/api/v1/overview",
        headers={"Authorization": ""},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_user_cannot_access_alert_operations(async_client: AsyncClient):
    response = await async_client.get(
        "/api/v1/alerts",
        headers=_headers("user"),
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_user_cannot_access_debug_stream(async_client: AsyncClient):
    response = await async_client.get(
        "/api/v1/stream",
        headers=_headers("user"),
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_http_only_cookie_can_authenticate_event_source(async_client: AsyncClient):
    token = create_access_token({"sub": "operator-cookie", "role": "operator"})
    response = await async_client.get(
        "/api/v1/auth/me",
        headers={"Authorization": ""},
        cookies={"access_token": token},
    )
    assert response.status_code == 200
    assert response.json()["role"] == "operator"


@pytest.mark.asyncio
async def test_operator_can_read_system_metrics(
    async_client: AsyncClient,
    monkeypatch,
):
    monkeypatch.setattr("api.routers.admin._query", lambda *_args, **_kwargs: [])
    response = await async_client.get(
        "/api/v1/admin/metrics/latency",
        headers=_headers("operator"),
    )
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_operator_cannot_manage_users(async_client: AsyncClient):
    response = await async_client.get(
        "/api/v1/admin/users",
        headers=_headers("operator"),
    )
    assert response.status_code == 403
