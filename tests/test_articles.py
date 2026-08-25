import pytest
from httpx import AsyncClient

@pytest.mark.asyncio
async def test_list_articles(async_client: AsyncClient):
    response = await async_client.get("/api/v1/articles")
    assert response.status_code == 200

    data = response.json()
    assert "total" in data
    assert "data" in data
    assert "page" in data
    assert data["total"] >= 3


@pytest.mark.asyncio
async def test_list_articles_with_source_filter(async_client: AsyncClient):
    response = await async_client.get("/api/v1/articles?source=vnexpress")
    assert response.status_code == 200

    data = response.json()
    for article in data["data"]:
        assert article["source"] == "vnexpress"


@pytest.mark.asyncio
async def test_list_articles_with_search(async_client: AsyncClient):
    response = await async_client.get("/api/v1/articles?q=AI")
    assert response.status_code == 200

    data = response.json()
    assert data["total"] >= 1
    assert "AI" in data["data"][0]["title"]


@pytest.mark.asyncio
async def test_list_articles_pagination(async_client: AsyncClient):
    response = await async_client.get("/api/v1/articles?page=1&page_size=2")
    assert response.status_code == 200

    data = response.json()
    assert data["page"] == 1
    assert data["page_size"] == 2
    assert len(data["data"]) <= 2


@pytest.mark.asyncio
async def test_get_article_detail(async_client: AsyncClient):
    response = await async_client.get("/api/v1/articles/90001")
    assert response.status_code == 200

    data = response.json()
    assert data["article_id"] == 90001
    assert data["title"] == "Test AI Article"
    assert data["source"] == "vnexpress"
    assert "keywords" in data
    assert "entities" in data
    assert len(data["keywords"]) == 2
    assert len(data["entities"]) == 2


@pytest.mark.asyncio
async def test_get_article_not_found(async_client: AsyncClient):
    response = await async_client.get("/api/v1/articles/99999")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_delete_article(async_client: AsyncClient):
    # Delete article 90003
    response = await async_client.delete("/api/v1/articles/90003")
    assert response.status_code == 200
    assert response.json()["article_id"] == 90003

    # Verify it's gone
    response = await async_client.get("/api/v1/articles/90003")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_delete_article_not_found(async_client: AsyncClient):
    response = await async_client.delete("/api/v1/articles/99999")
    assert response.status_code == 404