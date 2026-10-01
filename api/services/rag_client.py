"""Small REST clients for the optional on-premise RAG services."""

from datetime import datetime, timezone

import httpx

from api.config import get_settings
from api.exceptions import DependencyUnavailableError


def _call(service: str, method: str, url: str, *, json: dict | None = None) -> httpx.Response:
    try:
        response = httpx.request(
            method, url, json=json, timeout=get_settings().RAG_TIMEOUT_SECONDS
        )
        response.raise_for_status()
        return response
    except httpx.HTTPError as exc:
        raise DependencyUnavailableError(service) from exc


def embed(texts: list[str]) -> list[list[float]]:
    if not texts or len(texts) > 16:
        raise ValueError("Embedding batch size must be between 1 and 16")
    url = get_settings().EMBEDDING_URL.rstrip("/") + "/embed"
    try:
        vectors = _call("embedding", "POST", url, json={"texts": texts}).json()["vectors"]
    except (ValueError, KeyError, TypeError) as exc:
        raise DependencyUnavailableError("embedding") from exc
    if not isinstance(vectors, list) or len(vectors) != len(texts) or not all(
        isinstance(vector, list) and vector for vector in vectors
    ):
        raise DependencyUnavailableError("embedding")
    return vectors


def _collection_url() -> str:
    settings = get_settings()
    return settings.QDRANT_URL.rstrip("/") + "/collections/" + settings.QDRANT_COLLECTION


def ensure_collection(vector_size: int) -> None:
    url = _collection_url()
    try:
        response = httpx.get(url, timeout=get_settings().RAG_TIMEOUT_SECONDS)
    except httpx.HTTPError as exc:
        raise DependencyUnavailableError("qdrant") from exc
    if response.status_code == 404:
        _call("qdrant", "PUT", url, json={
            "vectors": {"size": vector_size, "distance": "Cosine"}
        })
        return
    try:
        response.raise_for_status()
        existing = response.json()["result"]["config"]["params"]["vectors"]["size"]
    except (httpx.HTTPError, ValueError, KeyError, TypeError) as exc:
        raise DependencyUnavailableError("qdrant") from exc
    if existing != vector_size:
        raise ValueError("Qdrant collection vector size does not match embedding model")


def delete_article(article_id: str) -> None:
    _call("qdrant", "POST", _collection_url() + "/points/delete?wait=true", json={
        "filter": {"must": [{"key": "article_id", "match": {"value": article_id}}]}
    })


def upsert_points(points: list[dict]) -> None:
    if points:
        _call("qdrant", "PUT", _collection_url() + "/points?wait=true", json={
            "points": points
        })


def query_chunks(
    vector: list[float], *, source: str | None, category: str | None,
    since: datetime, limit: int = 12,
) -> list[dict]:
    must = [{
        "key": "published_at_epoch",
        "range": {"gte": int(since.astimezone(timezone.utc).timestamp())},
    }]
    if source:
        must.append({"key": "source", "match": {"value": source}})
    if category:
        must.append({"key": "category", "match": {"value": category}})
    response = _call("qdrant", "POST", _collection_url() + "/points/query", json={
        "query": vector,
        "filter": {"must": must},
        "limit": min(max(limit, 1), 20),
        "with_payload": True,
        "with_vector": False,
    })
    try:
        return response.json()["result"]["points"]
    except (ValueError, KeyError, TypeError) as exc:
        raise DependencyUnavailableError("qdrant") from exc
