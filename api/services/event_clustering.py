"""Deterministic, bounded clustering for recent news events and duplicates."""

import hashlib
import re
import unicodedata
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException

from api.services.analytics import _query


STOPWORDS = {
    "va", "cua", "cho", "voi", "trong", "tren", "tai", "tu", "mot", "nhung",
    "cac", "the", "la", "co", "ve", "sau", "khi", "duoc", "news", "tin", "moi",
}


def _tokens(title: str) -> frozenset[str]:
    normalized = unicodedata.normalize("NFD", title.casefold())
    normalized = "".join(char for char in normalized if unicodedata.category(char) != "Mn").replace("đ", "d")
    return frozenset(
        word for word in re.findall(r"[a-z0-9]+", normalized)
        if len(word) >= 3 and word not in STOPWORDS
    )


def _similarity(left: frozenset[str], right: frozenset[str]) -> float:
    union = left | right
    return len(left & right) / len(union) if union else 0.0


def _load_articles(days: int, limit: int) -> list[dict]:
    since = datetime.now(timezone.utc) - timedelta(days=days)
    return _query(
        "SELECT url_hash AS article_id, title, url, source, category, "
        "publish_time AS published_at FROM newspulse.raw_articles FINAL "
        "WHERE publish_time >= {since:DateTime} AND title != '' "
        "ORDER BY publish_time DESC LIMIT {limit:UInt32}",
        {"since": since, "limit": limit},
    )


def cluster_events(days: int = 7, limit: int = 300) -> list[dict]:
    clusters: list[dict] = []
    for article in _load_articles(days, limit):
        token_set = _tokens(str(article.get("title", "")))
        if not token_set:
            continue
        best = None
        best_score = 0.0
        for cluster in clusters:
            score = _similarity(token_set, cluster["tokens"])
            if score > best_score:
                best, best_score = cluster, score
        if best is None or best_score < 0.34:
            clusters.append({"tokens": token_set, "articles": [article]})
        else:
            best["articles"].append(article)
            best["tokens"] = best["tokens"] | token_set

    results = []
    for cluster in clusters:
        articles = cluster["articles"]
        if len(articles) < 2:
            continue
        article_ids = sorted(str(item["article_id"]) for item in articles)
        event_id = hashlib.sha1("|".join(article_ids).encode()).hexdigest()[:16]
        duplicate_pairs = 0
        for index, article in enumerate(articles):
            current = _tokens(str(article.get("title", "")))
            if any(_similarity(current, _tokens(str(other.get("title", "")))) >= 0.72 for other in articles[:index]):
                duplicate_pairs += 1
        published_values = [item.get("published_at") for item in articles if item.get("published_at")]
        results.append({
            "event_id": event_id,
            "title": articles[0]["title"],
            "article_count": len(articles),
            "duplicate_count": duplicate_pairs,
            "sources": sorted({str(item.get("source", "")) for item in articles if item.get("source")}),
            "first_published_at": min(published_values) if published_values else None,
            "last_published_at": max(published_values) if published_values else None,
            "articles": articles[:20],
        })
    return sorted(
        results,
        key=lambda item: (
            item["article_count"],
            item["last_published_at"].timestamp() if hasattr(item["last_published_at"], "timestamp") else 0,
        ),
        reverse=True,
    )


def event_detail(event_id: str, days: int = 7) -> dict:
    event = next((item for item in cluster_events(days=days) if item["event_id"] == event_id), None)
    if event is None:
        raise HTTPException(status_code=404, detail="Event not found or outside the active window")
    return event
