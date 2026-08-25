import pytest
from httpx import AsyncClient

@pytest.mark.asyncio
async def test_top_entities(async_client: AsyncClient):
    response = await async_client.get("/api/v1/entities")
    assert response.status_code == 200

    data = response.json()
    assert isinstance(data, list)


@pytest.mark.asyncio
async def test_top_entities_filter_by_type(async_client: AsyncClient):
    response = await async_client.get(
        "/api/v1/entities?entity_type=LOC"
    )
    assert response.status_code == 200

    data = response.json()
    for entity in data:
        assert entity["entity_type"] == "LOC"


@pytest.mark.asyncio
async def test_entity_timeline(async_client: AsyncClient):
    # URL-encode Vietnamese characters
    response = await async_client.get(
        "/api/v1/entities/Google/timeline"
    )
    assert response.status_code == 200

    data = response.json()
    assert data["entity_name"] == "Google"
    assert "data" in data
    assert "entity_type" in data


@pytest.mark.asyncio
async def test_entities_by_category(async_client: AsyncClient):
    response = await async_client.get("/api/v1/entities/by-category")
    assert response.status_code == 200

    data = response.json()
    assert isinstance(data, list)
    if data:
        assert "category" in data[0]
        assert "entity_type" in data[0]
        assert "count" in data[0]


@pytest.mark.asyncio
async def test_entities_with_limit(async_client: AsyncClient):
    response = await async_client.get("/api/v1/entities?limit=2")
    assert response.status_code == 200

    data = response.json()
    assert len(data) <= 2


@pytest.mark.asyncio
async def test_entity_timeline_with_time_range(async_client: AsyncClient):
    response = await async_client.get(
        "/api/v1/entities/Google/timeline?time_range=30d"
    )
    assert response.status_code == 200