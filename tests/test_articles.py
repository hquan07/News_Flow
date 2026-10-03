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
    assert data["total"] == 2


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
@pytest.mark.parametrize("sentiment", ["positive", "neutral", "negative"])
async def test_list_articles_with_sentiment_filter(async_client: AsyncClient, sentiment: str):
    response = await async_client.get("/api/v1/articles", params={"sentiment": sentiment})

    assert response.status_code == 200
    for article in response.json()["data"]:
        expected = (
            "positive" if article["sentiment_score"] > 0 else
            "negative" if article["sentiment_score"] < 0 else "neutral"
        )
        assert expected == sentiment


@pytest.mark.asyncio
async def test_list_articles_combines_title_source_category_and_dates(
    async_client: AsyncClient,
):
    response = await async_client.get(
        "/api/v1/articles",
        params={
            "q": "AI",
            "source": "vnexpress",
            "category": "tech",
            "date_from": "2026-09-26",
            "date_to": "2026-09-26",
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert data["data"][0]["article_id"] == "hash_test_1"


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
    response = await async_client.get("/api/v1/articles/hash_test_1")
    assert response.status_code == 200

    data = response.json()
    assert data["article_id"] == "hash_test_1"
    assert data["title"] == "Test AI Article"
    assert data["source"] == "vnexpress"
    assert "keywords" in data
    assert "entities" in data
    assert len(data["keywords"]) == 2
    assert len(data["entities"]) == 0


@pytest.mark.asyncio
async def test_get_article_not_found(async_client: AsyncClient):
    response = await async_client.get("/api/v1/articles/missing")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_delete_article_is_not_exposed(async_client: AsyncClient):
    response = await async_client.delete("/api/v1/articles/hash_test_1")
    assert response.status_code == 405
