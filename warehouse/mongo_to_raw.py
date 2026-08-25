"""
mongo_to_raw.py — Load articles from MongoDB (articles_raw) into PostgreSQL (raw.articles).

Bridges Phase 1 (MongoDB raw storage) and Phase 2 (PostgreSQL ELT pipeline).
Self-contained config — reads env vars directly, no dependency on spark_config.

Usage:
    python -c "from warehouse.mongo_to_raw import run; run()"
"""

import hashlib
import os
from datetime import datetime

import psycopg2
import psycopg2.extras
from pymongo import MongoClient
from loguru import logger


# ── Config (self-contained — reads env vars directly) ───────
# Try PG_* first (used by .env/docker-compose), then POSTGRES_* fallback
PG_HOST = os.getenv("PG_HOST", os.getenv("POSTGRES_HOST", "postgres"))
PG_PORT = int(os.getenv("PG_PORT", os.getenv("POSTGRES_PORT", "5432")))
PG_DB = os.getenv("PG_DB", os.getenv("POSTGRES_DB", "newspulse"))
PG_USER = os.getenv("PG_USER", os.getenv("POSTGRES_USER", "newspulse"))
PG_PASSWORD = os.getenv("PG_PASSWORD", os.getenv("POSTGRES_PASSWORD", "newspulse"))

MONGO_URI = os.getenv("MONGO_URI", "mongodb://mongo:27017")
MONGO_DB = os.getenv("MONGO_DB", "newspulse")
MONGO_COLLECTION = os.getenv("MONGO_COLLECTION", "articles_raw")

BATCH_SIZE = 200


# ── Helpers ─────────────────────────────────────────────────────
def make_url_hash(url: str) -> str:
    return hashlib.md5(url.encode("utf-8")).hexdigest()


def parse_datetime(value) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    value = str(value).strip()
    if not value:
        return None
    for fmt in [
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d %H:%M:%S",
        "%d/%m/%Y %H:%M",
        "%Y-%m-%dT%H:%M:%S.%f%z",
        "%Y-%m-%dT%H:%M:%S.%f",
    ]:
        try:
            return datetime.strptime(value, fmt)
        except (ValueError, TypeError):
            continue
    logger.warning(f"Could not parse datetime: {value}")
    return None


def compute_word_count(content: str | None) -> int:
    if not content:
        return 0
    return len(content.split())


def compute_publish_hour(publish_time: datetime | None) -> int | None:
    return publish_time.hour if publish_time else None


def compute_crawl_latency(
    publish_time: datetime | None, crawl_time: datetime | None
) -> float | None:
    if publish_time is None or crawl_time is None:
        return None
    try:
        pt = publish_time.replace(tzinfo=None) if publish_time.tzinfo else publish_time
        ct = crawl_time.replace(tzinfo=None) if crawl_time.tzinfo else crawl_time
        delta = (ct - pt).total_seconds() / 60
        return round(delta, 1) if delta >= 0 else None
    except Exception:
        return None


# ── SQL ─────────────────────────────────────────────────────────
INSERT_SQL = """
INSERT INTO raw.articles (
    url, url_hash, title, content, author,
    publish_time, source, source_domain, category,
    word_count, keyword_count, publish_hour,
    crawl_latency_minutes, crawled_at, loaded_at
)
VALUES (
    %(url)s, %(url_hash)s, %(title)s, %(content)s, %(author)s,
    %(publish_time)s, %(source)s, %(source_domain)s, %(category)s,
    %(word_count)s, %(keyword_count)s, %(publish_hour)s,
    %(crawl_latency_minutes)s, %(crawled_at)s, NOW()
)
ON CONFLICT (url_hash) DO NOTHING;
"""


import sys
sys.path.append("/opt/airflow")
from kafka_utils import get_topic

def transform_document(doc: dict) -> dict | None:
    url = doc.get("url")
    title = doc.get("title")
    source = doc.get("source")
    if not url or not title or not source:
        return None

    content = doc.get("content", "")
    publish_time = parse_datetime(doc.get("publish_time"))
    crawl_time = parse_datetime(doc.get("crawl_time"))

    source_domain_map = {
        "VnExpress": "vnexpress.net",
        "vnexpress": "vnexpress.net",
        "Tuổi Trẻ": "tuoitre.vn",
        "tuoitre": "tuoitre.vn",
        "Thanh Niên": "thanhnien.vn",
        "thanhnien": "thanhnien.vn",
    }
    
    raw_category = doc.get("category", "")
    topic = get_topic(raw_category)
    category_normalized = topic.replace("news.", "")

    return {
        "url": url,
        "url_hash": make_url_hash(url),
        "title": title.strip(),
        "content": content,
        "author": (doc.get("author") or "").strip() or None,
        "publish_time": publish_time,
        "source": source,
        "source_domain": source_domain_map.get(source, f"{source.lower()}.vn"),
        "category": category_normalized,
        "word_count": compute_word_count(content),
        "keyword_count": 0,
        "publish_hour": compute_publish_hour(publish_time),
        "crawl_latency_minutes": compute_crawl_latency(publish_time, crawl_time),
        "crawled_at": crawl_time,
    }


def run() -> int:
    logger.info("=" * 60)
    logger.info("MongoDB → PostgreSQL raw.articles")
    logger.info(f"PG: {PG_USER}@{PG_HOST}:{PG_PORT}/{PG_DB}")
    logger.info(f"Mongo: {MONGO_URI}/{MONGO_DB}.{MONGO_COLLECTION}")
    logger.info("=" * 60)

    mongo_client = MongoClient(MONGO_URI)
    collection = mongo_client[MONGO_DB][MONGO_COLLECTION]

    total_docs = collection.count_documents({})
    logger.info(f"MongoDB: {total_docs} documents found")

    if total_docs == 0:
        logger.warning("No documents in MongoDB. Nothing to load.")
        mongo_client.close()
        return 0

    pg_conn = psycopg2.connect(
        host=PG_HOST,
        port=PG_PORT,
        dbname=PG_DB,
        user=PG_USER,
        password=PG_PASSWORD,
    )

    total_inserted = 0
    total_skipped = 0
    total_errors = 0

    try:
        cursor = collection.find({}, {"raw_html": 0})
        batch = []

        for doc in cursor:
            row = transform_document(doc)
            if row is None:
                total_skipped += 1
                continue
            batch.append(row)

            if len(batch) >= BATCH_SIZE:
                ins, err = _insert_batch(pg_conn, batch)
                total_inserted += ins
                total_errors += err
                batch = []

        if batch:
            ins, err = _insert_batch(pg_conn, batch)
            total_inserted += ins
            total_errors += err

    except Exception as e:
        logger.error(f"Fatal error: {e}")
        raise
    finally:
        pg_conn.close()
        mongo_client.close()

    logger.info("=" * 60)
    logger.info(f"Complete — inserted: {total_inserted}, skipped: {total_skipped}, errors: {total_errors}")
    logger.info("=" * 60)
    return total_inserted


def _insert_batch(conn, batch: list[dict]) -> tuple[int, int]:
    inserted = 0
    errors = 0
    try:
        with conn.cursor() as cur:
            for row in batch:
                try:
                    cur.execute(INSERT_SQL, row)
                    if cur.rowcount > 0:
                        inserted += 1
                except psycopg2.Error as e:
                    errors += 1
                    if errors <= 5:
                        logger.warning(f"Insert error for {row.get('url', '?')}: {e.pgerror or e}")
                    conn.rollback()
                    continue
            conn.commit()
    except Exception as e:
        conn.rollback()
        logger.error(f"Batch commit failed: {e}")
        errors += len(batch)

    if inserted > 0:
        logger.info(f"  Batch: {inserted} inserted, {errors} errors")
    return inserted, errors


if __name__ == "__main__":
    count = run()
    print(f"\nTotal loaded: {count} articles")