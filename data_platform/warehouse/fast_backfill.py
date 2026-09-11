"""
Fast backfill script: Load articles from JSON dump directly into ClickHouse.
Bypasses Spark entirely for maximum speed.
Applies the same text cleaning logic as the Spark pipeline.
"""
import json
import hashlib
import re
import unicodedata
from datetime import datetime, timezone
import clickhouse_connect


# ── Text cleaning functions (same logic as spark/processing/text_processor.py) ──

def clean_html(text: str) -> str:
    if not text:
        return ""
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"&[a-zA-Z]+;", " ", text)
    text = re.sub(r"&#\d+;", " ", text)
    text = re.sub(r"https?://\S+", "", text)
    text = unicodedata.normalize("NFC", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def word_count(text: str) -> int:
    if not text:
        return 0
    return len(text.split())


CATEGORY_MAP = {
    "thể thao": "sports", "the-thao": "sports", "bóng đá": "sports", "sports": "sports",
    "công nghệ": "tech", "cong-nghe": "tech", "số hóa": "tech", "khoa học": "tech",
    "khoa-hoc": "tech", "so-hoa": "tech", "tech": "tech", "technology": "tech",
    "kinh doanh": "economy", "kinh-doanh": "economy", "kinh tế": "economy",
    "tài chính": "economy", "bất động sản": "economy", "economy": "economy",
    "thời sự": "politics", "thoi-su": "politics", "chính trị": "politics", "politics": "politics",
    "giải trí": "entertainment", "giai-tri": "entertainment", "entertainment": "entertainment",
    "sức khỏe": "health", "suc-khoe": "health", "health": "health",
    "giáo dục": "education", "giao-duc": "education", "education": "education",
    "thế giới": "world", "the-gioi": "world", "world": "world",
    "pháp luật": "law", "phap-luat": "law", "law": "law",
    "đời sống": "general", "du lịch": "general",
}


def normalize_category(category: str) -> str:
    if not category:
        return "general"
    return CATEGORY_MAP.get(category.lower().strip(), "general")


def parse_datetime(dt_str: str) -> datetime:
    """Parse various datetime formats from the dump."""
    if not dt_str:
        return datetime.now(timezone.utc).replace(tzinfo=None)
    try:
        clean = dt_str.replace("Z", "+00:00")
        return datetime.fromisoformat(clean).replace(tzinfo=None)
    except Exception:
        pass
    # Try common Vietnamese formats
    for fmt in ["%d/%m/%Y %H:%M", "%Y-%m-%d %H:%M:%S", "%d/%m/%Y"]:
        try:
            return datetime.strptime(dt_str, fmt)
        except Exception:
            continue
    return datetime.now(timezone.utc).replace(tzinfo=None)


def md5_hash(url: str) -> str:
    if not url:
        return ""
    return hashlib.md5(url.encode()).hexdigest()


def process_article(raw: dict) -> dict:
    """Transform a raw article dict into a ClickHouse-ready row."""
    title_clean = clean_html(raw.get("title", ""))
    content_clean = clean_html(raw.get("content", ""))
    wc = word_count(content_clean)
    category = normalize_category(raw.get("category", ""))

    publish_dt = parse_datetime(raw.get("publish_time"))
    crawl_dt = parse_datetime(raw.get("crawl_time"))
    publish_hour = publish_dt.hour if publish_dt else 0

    crawl_latency = 0.0
    if publish_dt and crawl_dt:
        diff_seconds = (crawl_dt - publish_dt).total_seconds()
        crawl_latency = round(diff_seconds / 60, 1)
        if crawl_latency < 0:
            crawl_latency = 0.0

    return {
        "url_hash": raw.get("url_hash") or md5_hash(raw.get("url", "")),
        "url": raw.get("url", ""),
        "title": title_clean,
        "content": content_clean,
        "author": raw.get("author", "") or "",
        "publish_time": publish_dt,
        "source": raw.get("source", ""),
        "source_domain": "",
        "category": category,
        "word_count": wc,
        "keyword_count": 0,
        "publish_hour": publish_hour,
        "crawl_latency_minutes": crawl_latency,
        "crawled_at": crawl_dt,
        "loaded_at": datetime.now(timezone.utc).replace(tzinfo=None),
    }


def main():
    dump_file = "/home/hquan07/News_Flow/data_platform/warehouse/articles_dump.json"

    # Connect to ClickHouse (mapped port 8123)
    client = clickhouse_connect.get_client(
        host="localhost",
        port=8123,
        database="newspulse",
        username="admin",
        password="admin123",
    )

    # Get existing url_hashes to avoid duplicates
    print("Fetching existing url_hashes from ClickHouse...")
    existing = set()
    result = client.query("SELECT url_hash FROM newspulse.raw_articles")
    for row in result.result_rows:
        existing.add(row[0])
    print(f"Found {len(existing)} existing articles in ClickHouse.")

    # Load and process articles
    print("Loading articles from dump...")
    articles = []
    skipped = 0
    with open(dump_file, "r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            raw = json.loads(line)

            url_hash = raw.get("url_hash") or md5_hash(raw.get("url", ""))
            if url_hash in existing:
                skipped += 1
                continue

            # Skip articles with very short content (same as schema validation)
            content = raw.get("content", "")
            title = raw.get("title", "")
            if not content or len(content) < 100 or not title or len(title) < 5:
                skipped += 1
                continue

            processed = process_article(raw)
            articles.append(processed)
            existing.add(url_hash)  # prevent duplicates within the file

    print(f"Processed {len(articles)} new articles ({skipped} skipped/duplicate).")

    if not articles:
        print("Nothing to insert.")
        return

    # Insert in batches
    columns = [
        "url_hash", "url", "title", "content", "author", "publish_time",
        "source", "source_domain", "category", "word_count", "keyword_count",
        "publish_hour", "crawl_latency_minutes", "crawled_at", "loaded_at",
    ]

    batch_size = 5000
    total = len(articles)
    for i in range(0, total, batch_size):
        batch = articles[i:i + batch_size]
        rows = [tuple(art[c] for c in columns) for art in batch]
        client.insert("raw_articles", rows, column_names=columns)
        done = min(i + batch_size, total)
        print(f"Inserted {done}/{total} articles...")

    # Verify
    result = client.query("SELECT count() FROM newspulse.raw_articles")
    final_count = result.result_rows[0][0]
    print(f"\n✅ Done! ClickHouse now has {final_count} articles total.")


if __name__ == "__main__":
    main()
