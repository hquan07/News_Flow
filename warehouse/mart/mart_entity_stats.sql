CREATE SCHEMA IF NOT EXISTS mart;

DROP TABLE IF EXISTS mart.mart_entity_stats;

CREATE TABLE mart.mart_entity_stats (
    id              SERIAL PRIMARY KEY,
    entity_name     VARCHAR(255) NOT NULL,
    entity_type     VARCHAR(10) NOT NULL,  -- PER, LOC, ORG
    mention_count   INTEGER NOT NULL DEFAULT 0,
    article_count   INTEGER NOT NULL DEFAULT 0,
    sources         JSONB DEFAULT '[]'::jsonb,
    categories      JSONB DEFAULT '[]'::jsonb,
    first_seen      DATE,
    last_seen       DATE,
    period_start    DATE NOT NULL,
    period_end      DATE NOT NULL,
    created_at      TIMESTAMP DEFAULT NOW(),

    UNIQUE (entity_name, entity_type, period_start, period_end)
);

-- Populate: last 7 days
INSERT INTO mart.mart_entity_stats (
    entity_name, entity_type, mention_count, article_count,
    sources, categories, first_seen, last_seen,
    period_start, period_end
)
SELECT
    de.entity_name,
    de.entity_type,
    COUNT(*)                                    AS mention_count,
    COUNT(DISTINCT fa.article_id)               AS article_count,
    JSONB_AGG(DISTINCT ds.name)                 AS sources,
    JSONB_AGG(DISTINCT dc.name)                 AS categories,
    MIN(dt.date)                                AS first_seen,
    MAX(dt.date)                                AS last_seen,
    CURRENT_DATE - INTERVAL '7 days'            AS period_start,
    CURRENT_DATE                                AS period_end
FROM warehouse.bridge_article_entity bae
JOIN warehouse.dim_entity de ON bae.entity_id = de.entity_id
JOIN warehouse.fact_article fa ON bae.article_id = fa.article_id
JOIN warehouse.dim_source ds ON fa.source_id = ds.source_id
JOIN warehouse.dim_category dc ON fa.category_id = dc.category_id
JOIN warehouse.dim_time dt ON fa.time_id = dt.time_id
WHERE dt.date >= CURRENT_DATE - INTERVAL '7 days'
GROUP BY de.entity_name, de.entity_type
HAVING COUNT(*) >= 2  -- Filter noise: at least 2 mentions
ON CONFLICT (entity_name, entity_type, period_start, period_end)
DO UPDATE SET
    mention_count = EXCLUDED.mention_count,
    article_count = EXCLUDED.article_count,
    sources       = EXCLUDED.sources,
    categories    = EXCLUDED.categories,
    first_seen    = EXCLUDED.first_seen,
    last_seen     = EXCLUDED.last_seen,
    created_at    = NOW();

CREATE INDEX IF NOT EXISTS idx_entity_stats_type
    ON mart.mart_entity_stats (entity_type, mention_count DESC);

CREATE INDEX IF NOT EXISTS idx_entity_stats_period
    ON mart.mart_entity_stats (period_start, period_end);