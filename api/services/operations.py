from datetime import datetime, timezone

from fastapi import HTTPException

from api.services.analytics import _query


def article_lineage(article_id: str) -> dict:
    rows = _query(
        "SELECT a.url_hash AS article_id, a.title, a.source, a.url, a.crawled_at, a.loaded_at, "
        "k.keywords_at, e.entities_at, s.sentiment_at FROM newspulse.raw_articles AS a FINAL "
        "LEFT JOIN (SELECT url_hash, max(loaded_at) AS keywords_at FROM newspulse.raw_article_keywords GROUP BY url_hash) k USING (url_hash) "
        "LEFT JOIN (SELECT url_hash, max(loaded_at) AS entities_at FROM newspulse.raw_article_entities GROUP BY url_hash) e USING (url_hash) "
        "LEFT JOIN (SELECT url_hash, max(loaded_at) AS sentiment_at FROM newspulse.raw_article_sentiment GROUP BY url_hash) s USING (url_hash) "
        "WHERE a.url_hash = {article_id:String} LIMIT 1",
        {"article_id": article_id},
    )
    if not rows:
        raise HTTPException(status_code=404, detail="Article not found")
    article = rows[0]
    stages = [
        {"stage": "crawl", "status": "complete" if article.get("crawled_at") else "unknown", "timestamp": article.get("crawled_at")},
        {"stage": "warehouse", "status": "complete" if article.get("loaded_at") else "unknown", "timestamp": article.get("loaded_at")},
        {"stage": "keywords", "status": "complete" if article.get("keywords_at") else "missing", "timestamp": article.get("keywords_at")},
        {"stage": "entities", "status": "complete" if article.get("entities_at") else "missing", "timestamp": article.get("entities_at")},
        {"stage": "sentiment", "status": "complete" if article.get("sentiment_at") else "missing", "timestamp": article.get("sentiment_at")},
    ]
    return {
        "article": {key: article.get(key) for key in ("article_id", "title", "source", "url")},
        "stages": stages,
        "complete": all(stage["status"] == "complete" for stage in stages),
    }


def replay_payload(article_id: str) -> dict:
    rows = _query(
        "SELECT url_hash AS article_id, url, title, content, author, publish_time, crawled_at, source, category "
        "FROM newspulse.raw_articles FINAL WHERE url_hash = {article_id:String} LIMIT 1",
        {"article_id": article_id},
    )
    if not rows:
        raise HTTPException(status_code=404, detail="Article not found")
    row = rows[0]
    return {
        "url": row["url"], "title": row["title"], "content": row.get("content", ""),
        "author": row.get("author"), "publish_time": row.get("publish_time"),
        "crawled_time": row.get("crawled_at"), "source": row["source"], "category": row["category"],
        "replay": {"requested_at": datetime.now(timezone.utc).isoformat(), "original_article_id": article_id},
    }
