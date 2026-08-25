from loguru import logger
from warehouse.etl.db import get_connection


# 2a. Dimension upserts
UPSERT_DIM_AUTHOR_SQL = """
INSERT INTO warehouse.dim_author (name, source_id)
SELECT DISTINCT
    s.author,
    ds.source_id
FROM staging.articles s
JOIN warehouse.dim_source ds ON ds.name = s.source
WHERE s.author IS NOT NULL
  AND s.author != ''
  AND NOT EXISTS (
      SELECT 1 FROM warehouse.dim_author da
      WHERE da.name = s.author AND da.source_id = ds.source_id
  );
"""

UPDATE_AUTHOR_COUNT_SQL = """
UPDATE warehouse.dim_author da
SET
    article_count = sub.cnt,
    updated_at = NOW()
FROM (
    SELECT s.author, ds.source_id, COUNT(*) as cnt
    FROM staging.articles s
    JOIN warehouse.dim_source ds ON ds.name = s.source
    WHERE s.author IS NOT NULL
    GROUP BY s.author, ds.source_id
) sub
WHERE da.name = sub.author AND da.source_id = sub.source_id;
"""

UPSERT_DIM_KEYWORD_SQL = """
INSERT INTO warehouse.dim_keyword (keyword, first_seen_at, last_seen_at, total_count)
SELECT
    rk.keyword,
    MIN(rk.loaded_at),
    MAX(rk.loaded_at),
    COUNT(*)
FROM raw.article_keywords rk
GROUP BY rk.keyword
ON CONFLICT (keyword) DO UPDATE SET
    last_seen_at = GREATEST(warehouse.dim_keyword.last_seen_at, EXCLUDED.last_seen_at),
    total_count = warehouse.dim_keyword.total_count + EXCLUDED.total_count;
"""

UPSERT_DIM_ENTITY_SQL = """
INSERT INTO warehouse.dim_entity (entity_name, entity_type, first_seen_at, last_seen_at, mention_count)
SELECT
    re.entity,
    re.entity_type,
    MIN(re.loaded_at),
    MAX(re.loaded_at),
    COUNT(*)
FROM raw.article_entities re
GROUP BY re.entity, re.entity_type
ON CONFLICT (entity_name, entity_type) DO UPDATE SET
    last_seen_at = GREATEST(warehouse.dim_entity.last_seen_at, EXCLUDED.last_seen_at),
    mention_count = warehouse.dim_entity.mention_count + EXCLUDED.mention_count;
"""


# 2b. Fact table
STAGING_TO_FACT_SQL = """
INSERT INTO warehouse.fact_article (
    url_hash, source_id, category_id, time_id, author_id,
    word_count, keyword_count, publish_hour, crawl_latency_minutes,
    person_count, location_count, org_count,
    url, title, publish_time, sentiment_score, sentiment_label
)
SELECT
    s.url_hash,
    ds.source_id,
    dc.category_id,
    dt.time_id,
    da.author_id,
    s.word_count,
    s.keyword_count,
    s.publish_hour,
    s.crawl_latency_minutes,
    COALESCE(ent_counts.person_count, 0),
    COALESCE(ent_counts.location_count, 0),
    COALESCE(ent_counts.org_count, 0),
    s.url,
    s.title,
    s.publish_time,
    s.sentiment_score,
    s.sentiment_label
FROM staging.articles s
JOIN warehouse.dim_source ds ON ds.name = s.source
JOIN warehouse.dim_category dc ON dc.name = s.category
LEFT JOIN warehouse.dim_time dt ON dt.full_date = s.publish_time::DATE
LEFT JOIN warehouse.dim_author da
    ON da.name = s.author AND da.source_id = ds.source_id
LEFT JOIN (
    SELECT
        re.url_hash,
        SUM(CASE WHEN re.entity_type = 'person' THEN 1 ELSE 0 END) AS person_count,
        SUM(CASE WHEN re.entity_type = 'location' THEN 1 ELSE 0 END) AS location_count,
        SUM(CASE WHEN re.entity_type = 'organization' THEN 1 ELSE 0 END) AS org_count
    FROM raw.article_entities re
    GROUP BY re.url_hash
) ent_counts ON ent_counts.url_hash = s.url_hash
WHERE NOT EXISTS (
    SELECT 1 FROM warehouse.fact_article fa
    WHERE fa.url_hash = s.url_hash
);
"""


# 2c. Bridge tables
POPULATE_BRIDGE_KEYWORD_SQL = """
INSERT INTO warehouse.bridge_article_keyword (article_id, keyword_id, relevance_score)
SELECT
    fa.article_id,
    dk.keyword_id,
    MAX(rk.score)
FROM raw.article_keywords rk
JOIN warehouse.fact_article fa ON fa.url_hash = rk.url_hash
JOIN warehouse.dim_keyword dk ON dk.keyword = rk.keyword
GROUP BY fa.article_id, dk.keyword_id
ON CONFLICT (article_id, keyword_id) DO NOTHING;
"""

POPULATE_BRIDGE_ENTITY_SQL = """
INSERT INTO warehouse.bridge_article_entity (article_id, entity_id)
SELECT
    fa.article_id,
    de.entity_id
FROM raw.article_entities re
JOIN warehouse.fact_article fa ON fa.url_hash = re.url_hash
JOIN warehouse.dim_entity de
    ON de.entity_name = re.entity AND de.entity_type = re.entity_type
GROUP BY fa.article_id, de.entity_id
ON CONFLICT (article_id, entity_id) DO NOTHING;
"""


def run():
    logger.info("ELT Step 2: staging → warehouse")
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            # 2a. Dimensions
            logger.info("  2a. Upserting dimensions...")

            cur.execute(UPSERT_DIM_AUTHOR_SQL)
            logger.info(f"      dim_author: inserted {cur.rowcount} new authors")

            cur.execute(UPDATE_AUTHOR_COUNT_SQL)
            logger.info(f"      dim_author: updated {cur.rowcount} author counts")

            cur.execute(UPSERT_DIM_KEYWORD_SQL)
            logger.info(f"      dim_keyword: upserted {cur.rowcount} keywords")

            cur.execute(UPSERT_DIM_ENTITY_SQL)
            logger.info(f"      dim_entity: upserted {cur.rowcount} entities")

            # 2b. Fact
            logger.info("  2b. Inserting into fact_article...")
            cur.execute(STAGING_TO_FACT_SQL)
            fact_count = cur.rowcount
            logger.info(f"      fact_article: inserted {fact_count} rows")

            # 2c. Bridges
            logger.info("  2c. Populating bridge tables...")

            cur.execute(POPULATE_BRIDGE_KEYWORD_SQL)
            logger.info(f"      bridge_article_keyword: inserted {cur.rowcount} rows")

            cur.execute(POPULATE_BRIDGE_ENTITY_SQL)
            logger.info(f"      bridge_article_entity: inserted {cur.rowcount} rows")

            conn.commit()
            return fact_count

    except Exception as e:
        conn.rollback()
        logger.error(f"  staging → warehouse failed: {e}")
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    run()