from loguru import logger
from warehouse.etl.db import get_connection


RAW_TO_STAGING_SQL = """
INSERT INTO staging.articles (
    url, url_hash, title, content, author,
    publish_time, source, source_domain, category,
    word_count, keyword_count, publish_hour,
    crawl_latency_minutes, crawled_at, sentiment_score, sentiment_label, loaded_at, staged_at
)
SELECT
    r.url,
    r.url_hash,
    TRIM(r.title),
    r.content,
    NULLIF(TRIM(r.author), ''),
    r.publish_time,
    r.source,
    r.source_domain,
    r.category,
    COALESCE(r.word_count, 0),
    COALESCE(r.keyword_count, 0),
    r.publish_hour,
    r.crawl_latency_minutes,
    r.crawled_at,
    sent.sentiment_score,
    sent.sentiment_label,
    r.loaded_at,
    NOW()
FROM raw.articles r
LEFT JOIN (
    -- Get the most recent sentiment for each url_hash in case of duplicates
    SELECT DISTINCT ON (url_hash) url_hash, sentiment_score, sentiment_label
    FROM raw.article_sentiment
    ORDER BY url_hash, loaded_at DESC
) sent ON r.url_hash = sent.url_hash
WHERE r.url_hash IS NOT NULL
  AND r.title IS NOT NULL
  AND r.title != ''
  AND NOT EXISTS (
      SELECT 1 FROM staging.articles s
      WHERE s.url_hash = r.url_hash
  )
ORDER BY r.loaded_at;
"""


def run():
    logger.info("ELT Step 1: raw → staging")
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(RAW_TO_STAGING_SQL)
            count = cur.rowcount
            conn.commit()
            logger.info(f"  Inserted {count} new rows into staging.articles")
            return count
    except Exception as e:
        conn.rollback()
        logger.error(f"  raw → staging failed: {e}")
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    run()