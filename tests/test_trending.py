import pytest
from httpx import AsyncClient

@pytest.mark.asyncio
async def test_trending_keywords(async_client: AsyncClient):
    response = await async_client.get("/api/v1/trending/keywords")
    assert response.status_code == 200

    data = response.json()
    assert isinstance(data, list)


@pytest.mark.asyncio
async def test_trending_keywords_with_limit(async_client: AsyncClient):
    response = await async_client.get(
        "/api/v1/trending/keywords?limit=5"
    )
    assert response.status_code == 200

    data = response.json()
    assert len(data) <= 5


@pytest.mark.asyncio
async def test_keyword_timeline(async_client: AsyncClient):
    response = await async_client.get(
        "/api/v1/trending/keywords/AI/timeline"
    )
    assert response.status_code == 200

    data = response.json()
    assert data["keyword"] == "AI"
    assert "data" in data


@pytest.mark.asyncio
async def test_co_occurrences(async_client: AsyncClient):
    response = await async_client.get("/api/v1/trending/co-occurrences")
    assert response.status_code == 200

    data = response.json()
    assert isinstance(data, list)
    if data:
        assert "keyword_a" in data[0]
        assert "keyword_b" in data[0]
        assert "co_count" in data[0]