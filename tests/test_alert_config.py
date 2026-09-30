import pytest
from httpx import AsyncClient

from api.security import create_access_token
from api.services import alert_config


class _ConfigCollection:
    def __init__(self):
        self.document = None

    async def find_one(self, _query, _projection=None):
        return self.document

    async def update_one(self, _query, update, upsert=False):
        assert upsert is True
        self.document = update["$set"]


class _ConfigDb:
    def __init__(self):
        self.alert_config = _ConfigCollection()


def _admin_headers():
    token = create_access_token({"sub": "config-admin", "role": "admin"})
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_alert_thresholds_are_shared_in_mongodb(monkeypatch):
    database = _ConfigDb()
    monkeypatch.setattr(alert_config, "get_mongo_db", lambda: database)

    defaults = await alert_config.get_alert_thresholds()
    saved = await alert_config.update_alert_thresholds(
        {
            "crisis_negative_pct": 42.0,
            "crisis_min_posts": 20,
            "viral_interactions": 100,
        },
        "config-admin",
    )
    loaded = await alert_config.get_alert_thresholds()

    assert defaults["viral_interactions"] == 50
    assert saved["crisis_negative_pct"] == 42.0
    assert loaded["viral_interactions"] == 100


@pytest.mark.asyncio
async def test_alert_threshold_update_requires_admin(async_client: AsyncClient):
    response = await async_client.post(
        "/api/v1/alerts/config",
        headers={"Authorization": ""},
        json={
            "crisis_negative_pct": 30,
            "crisis_min_posts": 10,
            "viral_interactions": 50,
        },
    )

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_alert_threshold_endpoint_persists_admin_update(
    async_client: AsyncClient,
    monkeypatch,
):
    captured = {}

    async def fake_update(values, user_id):
        captured.update(values=values, user_id=user_id)
        return values

    monkeypatch.setattr("api.routers.alerts.update_alert_thresholds", fake_update)
    payload = {
        "crisis_negative_pct": 35,
        "crisis_min_posts": 12,
        "viral_interactions": 80,
    }

    response = await async_client.post(
        "/api/v1/alerts/config",
        json=payload,
        headers=_admin_headers(),
    )

    assert response.status_code == 200
    assert captured == {"values": payload, "user_id": "config-admin"}
