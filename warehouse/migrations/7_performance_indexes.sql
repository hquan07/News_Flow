-- ══════════════════════════════════════════════════════════════════════════════
-- 1. WAREHOUSE LAYER INDEXES — dashboard queries
-- ══════════════════════════════════════════════════════════════════════════════

-- Dashboard Overview: "số bài theo nguồn, theo category, theo ngày"
-- Query pattern: WHERE source_id = ? AND category_id = ? GROUP BY time_id
CREATE INDEX IF NOT EXISTS idx_fact_source_category_time
    ON warehouse.fact_article (source_id, category_id, time_id);

-- Dashboard Trending: "top keyword theo tuần" — join fact → bridge → dim_keyword
-- Covering index cho bridge table join
CREATE INDEX IF NOT EXISTS idx_bridge_keyword_article
    ON warehouse.bridge_article_keyword (keyword_id, article_id);

-- Dashboard Source Comparison: "so sánh tốc độ ra bài giữa các nguồn"
-- Query pattern: WHERE source_id = ? ORDER BY publish_time DESC
CREATE INDEX IF NOT EXISTS idx_fact_source_publish_time
    ON warehouse.fact_article (source_id, publish_time DESC);

-- Dashboard Alerts: spike detection — count by publish_time range
CREATE INDEX IF NOT EXISTS idx_fact_publish_time_source
    ON warehouse.fact_article (publish_time, source_id);

-- Entity analysis: "bài viết về entity X" — bridge join + filter
CREATE INDEX IF NOT EXISTS idx_bridge_entity_article
    ON warehouse.bridge_article_entity (entity_id, article_id);

-- dim_keyword: trending lookup
CREATE INDEX IF NOT EXISTS idx_dim_keyword_trending_count
    ON warehouse.dim_keyword (is_trending, total_count DESC)
    WHERE is_trending = TRUE;

-- dim_entity: type + mention count for "top entities" queries
-- Fixed: use correct column names from dim_entity schema
CREATE INDEX IF NOT EXISTS idx_dim_entity_type_mentions
    ON warehouse.dim_entity (entity_type, mention_count DESC);

-- Hourly distribution: publish_hour analysis
CREATE INDEX IF NOT EXISTS idx_fact_publish_hour_source
    ON warehouse.fact_article (publish_hour, source_id);


-- ══════════════════════════════════════════════════════════════════════════════
-- 2. STAGING LAYER INDEXES — tăng tốc ELT staging → warehouse
-- ══════════════════════════════════════════════════════════════════════════════

-- staging.articles: lookup by source for dimension matching
CREATE INDEX IF NOT EXISTS idx_staging_source_domain
    ON staging.articles (source, source_domain);

-- staging.articles: join condition khi load vào warehouse
CREATE INDEX IF NOT EXISTS idx_staging_url_hash_source
    ON staging.articles (url_hash, source);


-- ══════════════════════════════════════════════════════════════════════════════
-- 3. RAW LAYER INDEXES — tăng tốc raw → staging dedup
-- ══════════════════════════════════════════════════════════════════════════════

-- raw.articles: loaded_at for incremental processing
CREATE INDEX IF NOT EXISTS idx_raw_articles_loaded_at
    ON raw.articles (loaded_at DESC);

-- raw.article_keywords: composite for join
CREATE INDEX IF NOT EXISTS idx_raw_keywords_hash_keyword
    ON raw.article_keywords (url_hash, keyword);

-- raw.article_entities: composite for join
CREATE INDEX IF NOT EXISTS idx_raw_entities_hash_type
    ON raw.article_entities (url_hash, entity_type);


-- ══════════════════════════════════════════════════════════════════════════════
-- 4. MATERIALIZED VIEWS — pre-computed aggregations for dashboards
-- ══════════════════════════════════════════════════════════════════════════════

-- Daily article count by source and category (Overview dashboard)
CREATE MATERIALIZED VIEW IF NOT EXISTS mart.mv_daily_source_category AS
SELECT
    dt.full_date,
    ds.name AS source_name,
    dc.name AS category_name,
    COUNT(*) AS article_count,
    AVG(fa.word_count) AS avg_word_count
FROM warehouse.fact_article fa
JOIN warehouse.dim_time dt ON fa.time_id = dt.time_id
JOIN warehouse.dim_source ds ON fa.source_id = ds.source_id
JOIN warehouse.dim_category dc ON fa.category_id = dc.category_id
GROUP BY dt.full_date, ds.name, dc.name;

CREATE UNIQUE INDEX IF NOT EXISTS idx_mv_daily_source_cat
    ON mart.mv_daily_source_category (full_date, source_name, category_name);

-- Hourly distribution (Overview dashboard)
CREATE MATERIALIZED VIEW IF NOT EXISTS mart.mv_hourly_distribution AS
SELECT
    fa.publish_hour,
    ds.name AS source_name,
    COUNT(*) AS article_count
FROM warehouse.fact_article fa
JOIN warehouse.dim_source ds ON fa.source_id = ds.source_id
WHERE fa.publish_hour IS NOT NULL
GROUP BY fa.publish_hour, ds.name;

CREATE UNIQUE INDEX IF NOT EXISTS idx_mv_hourly_dist
    ON mart.mv_hourly_distribution (publish_hour, source_name);


-- ══════════════════════════════════════════════════════════════════════════════
-- 5. REFRESH FUNCTION — call from Airflow DAG
-- ══════════════════════════════════════════════════════════════════════════════

CREATE OR REPLACE FUNCTION mart.refresh_materialized_views()
RETURNS void AS $$
BEGIN
    REFRESH MATERIALIZED VIEW CONCURRENTLY mart.mv_daily_source_category;
    REFRESH MATERIALIZED VIEW CONCURRENTLY mart.mv_hourly_distribution;
END;
$$ LANGUAGE plpgsql;
