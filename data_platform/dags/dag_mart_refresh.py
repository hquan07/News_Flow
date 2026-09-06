from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.providers.postgres.operators.postgres import PostgresOperator


# ── SQL: mart.daily_overview ──────────────────────────────────
REFRESH_DAILY_OVERVIEW = """
DELETE FROM mart.daily_overview
WHERE date >= CURRENT_DATE - INTERVAL '7 days';

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

# ── SQL: mart.hourly_distribution ─────────────────────────────
REFRESH_HOURLY_DISTRIBUTION = """
DELETE FROM mart.hourly_distribution
WHERE date >= CURRENT_DATE - INTERVAL '7 days';

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

# ── SQL: mart.trending_keywords ───────────────────────────────
REFRESH_TRENDING_KEYWORDS = """
DELETE FROM mart.trending_keywords
WHERE week_start >= DATE_TRUNC('week', CURRENT_DATE) - INTERVAL '1 week';

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
    SELECT dk.keyword, COUNT(*) AS mention_count
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
        ELSE ROUND((cw.mention_count - pw.mention_count)::NUMERIC / pw.mention_count * 100, 2)
    END AS spike_score
FROM current_week cw
LEFT JOIN prev_week pw ON pw.keyword = cw.keyword
ORDER BY spike_score DESC
ON CONFLICT (week_start, keyword) DO UPDATE SET
    mention_count = EXCLUDED.mention_count,
    prev_week_count = EXCLUDED.prev_week_count,
    spike_score = EXCLUDED.spike_score;
"""

# ── SQL: mart.source_comparison ───────────────────────────────
REFRESH_SOURCE_COMPARISON = """
DELETE FROM mart.source_comparison
WHERE date >= CURRENT_DATE - INTERVAL '7 days';

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


# ── DAG Definition ────────────────────────────────────────────
default_args = {
    "owner": "newspulse",
    "depends_on_past": False,
    "retries": 2,
    "retry_delay": timedelta(minutes=5),
}

with DAG(
    dag_id="mart_refresh",
    default_args=default_args,
    description="Refresh mart tables from warehouse",
    schedule_interval="0 */6 * * *",  # Every 6 hours
    start_date=datetime(2024, 1, 1),
    catchup=False,
    tags=["mart", "elt"],
) as dag:

    refresh_daily = PostgresOperator(
        task_id="refresh_daily_overview",
        postgres_conn_id="newspulse_pg",
        sql=REFRESH_DAILY_OVERVIEW,
    )

    refresh_hourly = PostgresOperator(
        task_id="refresh_hourly_distribution",
        postgres_conn_id="newspulse_pg",
        sql=REFRESH_HOURLY_DISTRIBUTION,
    )

    refresh_trending = PostgresOperator(
        task_id="refresh_trending_keywords",
        postgres_conn_id="newspulse_pg",
        sql=REFRESH_TRENDING_KEYWORDS,
    )

    refresh_source = PostgresOperator(
        task_id="refresh_source_comparison",
        postgres_conn_id="newspulse_pg",
        sql=REFRESH_SOURCE_COMPARISON,
    )

    # All mart refreshes run in parallel
    [refresh_daily, refresh_hourly, refresh_trending, refresh_source]
