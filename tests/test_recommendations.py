import pytest
from httpx import AsyncClient

from api.security import create_access_token


def _auth_headers():
    token = create_access_token({"sub": "recommendation-user", "role": "user"})
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_recommendations_without_trailing_slash_do_not_redirect(
    async_client: AsyncClient,
    monkeypatch,
):
    article = {
        "url_hash": "recommended-hash",
        "url": "https://example.com/recommended",
        "title": "Recommended article",
        "content": "Article content",
        "author": "Author",
        "source": "example",
        "category": "tech",
        "publish_time": "2026-09-29T12:00:00",
    }

    def fake_query(sql, _params=None):
        if "user_interactions" in sql:
            return [{"article_hash": "already-read"}]
        return [article]

    monkeypatch.setattr("api.routers.recommendations._query", fake_query)

    response = await async_client.get(
        "/api/v1/recommendations",
        headers=_auth_headers(),
        follow_redirects=False,
    )

    assert response.status_code == 200
    assert response.json()["articles"] == [article]


@pytest.mark.asyncio
async def test_recommendations_keep_trailing_slash_compatibility(
    async_client: AsyncClient,
    monkeypatch,
):
    monkeypatch.setattr("api.routers.recommendations._query", lambda *_args, **_kwargs: [])

    response = await async_client.get(
        "/api/v1/recommendations/",
        headers=_auth_headers(),
        follow_redirects=False,
    )

    assert response.status_code == 200
    assert response.json() == {"articles": []}
