"""Idempotently index recent, public ClickHouse articles into Qdrant."""

import argparse
import hashlib
import logging
import time
from datetime import datetime, timedelta, timezone
from uuid import NAMESPACE_URL, uuid5

from pymongo import MongoClient

from api.config import get_settings
from api.services.analytics import _query
from api.services import rag_client


logger = logging.getLogger(__name__)


def chunks(content: str, *, size: int = 900, overlap: int = 120) -> list[str]:
    text = " ".join(content.split())[:30000]
    if not text:
        return []
    result = []
    start = 0
    while start < len(text):
        end = min(start + size, len(text))
        if end < len(text):
            boundary = text.rfind(" ", start + size // 2, end)
            if boundary > start:
                end = boundary
        result.append(text[start:end].strip())
        if end == len(text):
            break
        start = max(start + 1, end - overlap)
    return [part for part in result if part]


def _fingerprint(article: dict) -> str:
    fields = ("title", "content", "url", "source", "category", "publish_time")
    serialized = "\x1f".join(str(article.get(key, "")) for key in fields)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def _published_epoch(value: datetime) -> int:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return int(value.timestamp())


def index_article(article: dict, state) -> bool:
    article_id = str(article["url_hash"])
    if not article_id or not str(article.get("url", "")).startswith(("https://", "http://")):
        return False
    parts = chunks(article.get("content") or "")
    if not parts:
        return False
    digest = _fingerprint(article)
    previous = state.find_one({"_id": article_id})
    if previous and previous.get("fingerprint") == digest:
        return False
    vectors = []
    for start in range(0, len(parts), 16):
        vectors.extend(rag_client.embed(parts[start:start + 16]))
    rag_client.ensure_collection(len(vectors[0]))
    epoch = _published_epoch(article["publish_time"])
    points = [{
        "id": str(uuid5(NAMESPACE_URL, f"newspulse:{article_id}:{index}")),
        "vector": vector,
        "payload": {
            "article_id": article_id,
            "source": article["source"],
            "category": article["category"],
            "published_at_epoch": epoch,
            "text": part,
        },
    } for index, (part, vector) in enumerate(zip(parts, vectors))]
    rag_client.delete_article(article_id)
    for start in range(0, len(points), 16):
        rag_client.upsert_points(points[start:start + 16])
    state.update_one(
        {"_id": article_id},
        {"$set": {"fingerprint": digest, "indexed_at": datetime.now(timezone.utc)}},
        upsert=True,
    )
    return True


def index_recent(*, since_days: int = 30, limit: int = 2000) -> dict:
    settings = get_settings()
    since = datetime.now(timezone.utc) - timedelta(days=since_days)
    client = MongoClient(settings.mongo_url, serverSelectionTimeoutMS=5000)
    scanned = indexed = 0
    last_time = None
    last_id = None
    try:
        state = client[settings.MONGO_DB]["rag_index_state"]
        while scanned < limit:
            params = {"since": since, "batch_limit": min(100, limit - scanned)}
            cursor_filter = ""
            if last_time is not None:
                cursor_filter = (
                    " AND (publish_time < {last_time:DateTime} OR "
                    "(publish_time = {last_time:DateTime} AND url_hash < {last_id:String}))"
                )
                params.update(last_time=last_time, last_id=last_id)
            rows = _query(
                "SELECT url_hash, url, title, content, source, category, publish_time "
                "FROM newspulse.raw_articles FINAL "
                "WHERE publish_time >= {since:DateTime}" + cursor_filter +
                " ORDER BY publish_time DESC, url_hash DESC LIMIT {batch_limit:UInt32}",
                params,
            )
            if not rows:
                break
            for row in rows:
                indexed += int(index_article(row, state))
            scanned += len(rows)
            last_time, last_id = rows[-1]["publish_time"], rows[-1]["url_hash"]
        return {"scanned": scanned, "indexed": indexed}
    finally:
        client.close()


def main():
    parser = argparse.ArgumentParser(description="Index ClickHouse articles for RAG")
    parser.add_argument("--since-days", type=int, default=30)
    parser.add_argument("--limit", type=int, default=2000)
    parser.add_argument("--loop", type=int, default=0, metavar="SECONDS")
    args = parser.parse_args()
    if args.since_days < 1 or args.limit < 1 or args.loop < 0:
        parser.error("since-days and limit must be positive; loop must be nonnegative")
    logging.basicConfig(level=logging.INFO)
    while True:
        try:
            logger.info("RAG indexing result: %s", index_recent(since_days=args.since_days, limit=args.limit))
        except Exception:
            logger.exception("RAG indexing failed")
            if not args.loop:
                raise
        if not args.loop:
            return
        time.sleep(args.loop)


if __name__ == "__main__":
    main()
