from loguru import logger
from warehouse.etl.db import get_connection

# mart.daily_overview
REFRESH_DAILY_OVERVIEW_SQL = """
INSERT INTO mart.daily_overview (date, source, category, article_count, avg_word_count, avg_crawl_latency)
SELECT
    dt.full_date AS date,
    ds.name AS source,
    dc.name AS category,
    COUNT(*) AS article_count,
    ROUND(AVG(fa.word_count), 1) AS avg_word_count,
    ROUND(AVG(fa.crawl_latency_minutes), 1) AS avg_crawl_latency
FROM warehouse.fact_article fa
JOIN warehouse.dim_source ds ON ds.source_id = fa.source_id
JOIN warehouse.dim_category dc ON dc.category_id = fa.category_id
JOIN warehouse.dim_time dt ON dt.time_id = fa.time_id
WHERE dt.full_date >= CURRENT_DATE - INTERVAL '7 days'
GROUP BY dt.full_date, ds.name, dc.name
ON CONFLICT (date, source, category) DO UPDATE SET
    article_count = EXCLUDED.article_count,
    avg_word_count = EXCLUDED.avg_word_count,
    avg_crawl_latency = EXCLUDED.avg_crawl_latency;
"""


# mart.trending_keywords
REFRESH_TRENDING_KEYWORDS_SQL = """
INSERT INTO mart.trending_keywords (week_start, keyword, mention_count, prev_week_count, spike_score)
WITH current_week AS (
    SELECT
        DATE_TRUNC('week', CURRENT_DATE)::DATE AS week_start,
        dk.keyword,
        COUNT(*) AS mention_count
    FROM warehouse.bridge_article_keyword bak
    JOIN warehouse.dim_keyword dk ON dk.keyword_id = bak.keyword_id
    JOIN warehouse.fact_article fa ON fa.article_id = bak.article_id
    WHERE fa.publish_time >= DATE_TRUNC('week', CURRENT_DATE)
    GROUP BY dk.keyword
),
prev_week AS (
    SELECT
        dk.keyword,
        COUNT(*) AS mention_count
    FROM warehouse.bridge_article_keyword bak
    JOIN warehouse.dim_keyword dk ON dk.keyword_id = bak.keyword_id
    JOIN warehouse.fact_article fa ON fa.article_id = bak.article_id
    WHERE fa.publish_time >= DATE_TRUNC('week', CURRENT_DATE) - INTERVAL '1 week'
      AND fa.publish_time < DATE_TRUNC('week', CURRENT_DATE)
    GROUP BY dk.keyword
)
SELECT
    cw.week_start,
    cw.keyword,
    cw.mention_count,
    COALESCE(pw.mention_count, 0) AS prev_week_count,
    CASE
        WHEN COALESCE(pw.mention_count, 0) = 0 THEN cw.mention_count::NUMERIC
        ELSE ROUND(
            (cw.mention_count - pw.mention_count)::NUMERIC / pw.mention_count * 100, 2
        )
    END AS spike_score
FROM current_week cw
LEFT JOIN prev_week pw ON pw.keyword = cw.keyword
ORDER BY spike_score DESC
ON CONFLICT (week_start, keyword) DO UPDATE SET
    mention_count = EXCLUDED.mention_count,
    prev_week_count = EXCLUDED.prev_week_count,
    spike_score = EXCLUDED.spike_score;
"""


# mart.source_comparison
REFRESH_SOURCE_COMPARISON_SQL = """
INSERT INTO mart.source_comparison (date, source, total_articles, avg_publish_hour, top_category, avg_word_count)
SELECT
    dt.full_date AS date,
    ds.name AS source,
    COUNT(*) AS total_articles,
    ROUND(AVG(fa.publish_hour), 1) AS avg_publish_hour,
    MODE() WITHIN GROUP (ORDER BY dc.name) AS top_category,
    ROUND(AVG(fa.word_count), 1) AS avg_word_count
FROM warehouse.fact_article fa
JOIN warehouse.dim_source ds ON ds.source_id = fa.source_id
JOIN warehouse.dim_category dc ON dc.category_id = fa.category_id
JOIN warehouse.dim_time dt ON dt.time_id = fa.time_id
WHERE dt.full_date >= CURRENT_DATE - INTERVAL '7 days'
GROUP BY dt.full_date, ds.name
ON CONFLICT (date, source) DO UPDATE SET
    total_articles = EXCLUDED.total_articles,
    avg_publish_hour = EXCLUDED.avg_publish_hour,
    top_category = EXCLUDED.top_category,
    avg_word_count = EXCLUDED.avg_word_count;
"""


# ============================================================
# mart.hourly_distribution
REFRESH_HOURLY_DISTRIBUTION_SQL = """
INSERT INTO mart.hourly_distribution (date, hour, source, article_count)
SELECT
    dt.full_date AS date,
    fa.publish_hour AS hour,
    ds.name AS source,
    COUNT(*) AS article_count
FROM warehouse.fact_article fa
JOIN warehouse.dim_source ds ON ds.source_id = fa.source_id
JOIN warehouse.dim_time dt ON dt.time_id = fa.time_id
WHERE dt.full_date >= CURRENT_DATE - INTERVAL '7 days'
  AND fa.publish_hour IS NOT NULL
GROUP BY dt.full_date, fa.publish_hour, ds.name
ON CONFLICT (date, hour, source) DO UPDATE SET
    article_count = EXCLUDED.article_count;
"""
REFRESH_ENTITY_TRENDING_SQL = """
INSERT INTO mart.entity_trending (date, entity, entity_type, mention_count, article_count)
SELECT
    dt.full_date AS date,
    de.entity_name AS entity,
    de.entity_type,
    COUNT(*) AS mention_count,
    COUNT(DISTINCT fa.article_id) AS article_count
FROM warehouse.bridge_article_entity bae
JOIN warehouse.dim_entity de ON de.entity_id = bae.entity_id
JOIN warehouse.fact_article fa ON fa.article_id = bae.article_id
JOIN warehouse.dim_time dt ON dt.time_id = fa.time_id
WHERE dt.full_date >= CURRENT_DATE - INTERVAL '7 days'
GROUP BY dt.full_date, de.entity_name, de.entity_type
ON CONFLICT (date, entity, entity_type) DO UPDATE SET
    mention_count = EXCLUDED.mention_count,
    article_count = EXCLUDED.article_count;
"""

REFRESH_ENTITY_NETWORK_SQL = """
INSERT INTO mart.entity_network (date, entity_a, entity_b, co_occurrence_count)
SELECT 
    dt.full_date AS date,
    de1.entity_name AS entity_a,
    de2.entity_name AS entity_b,
    COUNT(DISTINCT fa.article_id) AS co_occurrence_count
FROM warehouse.fact_article fa
JOIN warehouse.dim_time dt ON dt.time_id = fa.time_id
JOIN warehouse.bridge_article_entity bae1 ON fa.article_id = bae1.article_id
JOIN warehouse.bridge_article_entity bae2 ON fa.article_id = bae2.article_id AND bae1.entity_id < bae2.entity_id
JOIN warehouse.dim_entity de1 ON de1.entity_id = bae1.entity_id
JOIN warehouse.dim_entity de2 ON de2.entity_id = bae2.entity_id
WHERE dt.full_date >= CURRENT_DATE - INTERVAL '7 days'
GROUP BY dt.full_date, de1.entity_name, de2.entity_name
ON CONFLICT (date, entity_a, entity_b) DO UPDATE SET
    co_occurrence_count = EXCLUDED.co_occurrence_count;
"""

def run():
    logger.info("ELT Step 3: warehouse → mart")
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(REFRESH_DAILY_OVERVIEW_SQL)
            logger.info(f"  mart.daily_overview: refreshed ({cur.rowcount} rows)")

            cur.execute(REFRESH_TRENDING_KEYWORDS_SQL)
            logger.info(f"  mart.trending_keywords: refreshed ({cur.rowcount} rows)")

            cur.execute(REFRESH_ENTITY_TRENDING_SQL)
            logger.info(f"  mart.entity_trending: refreshed ({cur.rowcount} rows)")
            
            cur.execute(REFRESH_ENTITY_NETWORK_SQL)
            logger.info(f"  mart.entity_network: refreshed ({cur.rowcount} rows)")

            cur.execute(REFRESH_SOURCE_COMPARISON_SQL)
            logger.info(f"  mart.source_comparison: refreshed ({cur.rowcount} rows)")

            cur.execute(REFRESH_HOURLY_DISTRIBUTION_SQL)
            logger.info(f"  mart.hourly_distribution: refreshed ({cur.rowcount} rows)")

            conn.commit()
            logger.info("  All mart tables refreshed successfully")

    except Exception as e:
        conn.rollback()
        logger.error(f"  warehouse → mart failed: {e}")
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    run()