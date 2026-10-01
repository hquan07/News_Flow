from types import SimpleNamespace

import pytest

from api.routers.admin import MOCK_SCENARIOS
from api.security import create_access_token


@pytest.mark.asyncio
async def test_mock_scenarios_are_admin_only(async_client):
    user_token = create_access_token({"sub": "regular-user", "role": "user"})
    headers = {"Authorization": f"Bearer {user_token}"}
    assert (await async_client.get("/api/v1/admin/mock/social/scenarios", headers=headers)).status_code == 403
    assert (await async_client.post("/api/v1/admin/mock/social?count=10", headers=headers)).status_code == 403


@pytest.mark.asyncio
async def test_mock_scenario_preview_does_not_insert(async_client, monkeypatch):
    def no_insert(_callback):
        raise AssertionError("Preview must not write data")

    monkeypatch.setattr("api.routers.admin.execute_clickhouse", no_insert)
    response = await async_client.get("/api/v1/admin/mock/social/scenarios")
    assert response.status_code == 200
    assert {scenario["id"] for scenario in response.json()["scenarios"]} == set(MOCK_SCENARIOS)


@pytest.mark.asyncio
@pytest.mark.parametrize("scenario", list(MOCK_SCENARIOS))
async def test_mock_scenario_generates_matching_rows(async_client, monkeypatch, scenario):
    inserted = {}

    def capture_insert(callback):
        def insert(table, rows, column_names):
            inserted.update(table=table, rows=rows, columns=column_names)

        callback(SimpleNamespace(insert=insert))

    monkeypatch.setattr("api.routers.admin.execute_clickhouse", capture_insert)
    response = await async_client.post(f"/api/v1/admin/mock/social?count=12&scenario={scenario}")
    assert response.status_code == 200
    assert response.json()["scenario"] == scenario
    assert inserted["table"] == "newspulse.social_sentiment_metrics"
    assert len(inserted["rows"]) == 12

    config = MOCK_SCENARIOS[scenario]
    for index, row in enumerate(inserted["rows"]):
        assert row[0].startswith("live_post_")
        assert row[1] == config["sources"][index % len(config["sources"])]
        assert row[2].startswith("[MOCK] ")
        assert scenario in row[3]
        assert config["like_range"][0] <= row[4] <= config["like_range"][1]
        assert config["reply_range"][0] <= row[6] <= config["reply_range"][1]
        assert row[8] == config["sentiments"][index % len(config["sentiments"])]
        if row[8] == "positive":
            assert row[7] >= 0.25
        elif row[8] == "negative":
            assert row[7] <= -0.5
        else:
            assert -0.15 <= row[7] <= 0.15


@pytest.mark.asyncio
async def test_mock_scenario_rejects_unknown_value(async_client):
    response = await async_client.post("/api/v1/admin/mock/social?count=10&scenario=unknown")
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_mock_scenario_keeps_default_and_count_limit(async_client, monkeypatch):
    inserted = []

    def capture_insert(callback):
        callback(SimpleNamespace(insert=lambda _table, rows, column_names: inserted.extend(rows)))

    monkeypatch.setattr("api.routers.admin.execute_clickhouse", capture_insert)
    response = await async_client.post("/api/v1/admin/mock/social?count=1")
    assert response.status_code == 200
    assert response.json()["scenario"] == "balanced"
    assert len(inserted) == 1
    assert (await async_client.post("/api/v1/admin/mock/social?count=1001")).status_code == 422
