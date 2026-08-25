import pytest
from httpx import AsyncClient

@pytest.mark.asyncio
async def test_overview_default(async_client: AsyncClient):
    response = await async_client.get("/api/v1/overview")
    assert response.status_code == 200

    data = response.json()
    assert "kpi_cards" in data
    assert "articles_by_hour" in data
    assert "category_distribution" in data
    assert "source_speed" in data


@pytest.mark.asyncio
async def test_overview_kpi_cards(async_client: AsyncClient):
    response = await async_client.get("/api/v1/overview?time_range=today")
    data = response.json()

    labels = [card["label"] for card in data["kpi_cards"]]
    assert "Total articles" in labels
    assert "Active sources" in labels
    assert "Top category" in labels


@pytest.mark.asyncio
async def test_overview_hourly_distribution(async_client: AsyncClient):
    response = await async_client.get("/api/v1/overview?time_range=today")
    data = response.json()

    if data["articles_by_hour"]:
        entry = data["articles_by_hour"][0]
        assert "hour" in entry
        assert "count" in entry


@pytest.mark.asyncio
async def test_overview_time_range_7d(async_client: AsyncClient):
    response = await async_client.get("/api/v1/overview?time_range=7d")
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_overview_time_range_30d(async_client: AsyncClient):
    response = await async_client.get("/api/v1/overview?time_range=30d")
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_overview_category_distribution(async_client: AsyncClient):
    response = await async_client.get("/api/v1/overview?time_range=today")
    data = response.json()

    if data["category_distribution"]:
        entry = data["category_distribution"][0]
        assert "category" in entry
        assert "count" in entry