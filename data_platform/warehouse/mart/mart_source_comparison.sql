CREATE SCHEMA IF NOT EXISTS mart;

DROP TABLE IF EXISTS mart.mart_source_comparison;

CREATE TABLE mart.mart_source_comparison (
    id              SERIAL PRIMARY KEY,
    report_date     DATE NOT NULL,
    source_a        VARCHAR(100) NOT NULL,
    source_b        VARCHAR(100) NOT NULL,
    overlap_count   INTEGER NOT NULL DEFAULT 0,
    overlap_rate    NUMERIC(5, 2) DEFAULT 0.0,
    total_a         INTEGER NOT NULL DEFAULT 0,
    total_b         INTEGER NOT NULL DEFAULT 0,
    created_at      TIMESTAMP DEFAULT NOW(),

    UNIQUE (report_date, source_a, source_b)
);

-- Populate: pairwise source overlap for recent dates
INSERT INTO mart.mart_source_comparison (
    report_date, source_a, source_b,
    overlap_count, overlap_rate, total_a, total_b
)
WITH article_keywords AS (
    -- Each article with its source and keyword set
    SELECT
        fa.article_id,
        ds.name AS source_name,
        dt.date AS publish_date,
        ARRAY_AGG(dk.keyword ORDER BY dk.keyword) AS keywords
    FROM warehouse.fact_article fa
    JOIN warehouse.dim_source ds ON fa.source_id = ds.source_id
    JOIN warehouse.dim_time dt ON fa.time_id = dt.time_id
    JOIN warehouse.bridge_article_keyword bak ON fa.article_id = bak.article_id
    JOIN warehouse.dim_keyword dk ON bak.keyword_id = dk.keyword_id
    WHERE dt.date >= CURRENT_DATE - INTERVAL '7 days'
    GROUP BY fa.article_id, ds.name, dt.date
),
source_pairs AS (
    -- Find article pairs from different sources on same day
    -- sharing >= 3 keywords
    SELECT
        a1.publish_date,
        a1.source_name AS source_a,
        a2.source_name AS source_b,
        COUNT(*) AS overlap_count
    FROM article_keywords a1
    JOIN article_keywords a2
        ON a1.publish_date = a2.publish_date
        AND a1.source_name < a2.source_name
    WHERE (
        SELECT COUNT(*)
        FROM unnest(a1.keywords) k1
        WHERE k1 = ANY(a2.keywords)
    ) >= 3
    GROUP BY a1.publish_date, a1.source_name, a2.source_name
),
source_totals AS (
    SELECT
        publish_date,
        source_name,
        COUNT(DISTINCT article_id) AS total_articles
    FROM article_keywords
    GROUP BY publish_date, source_name
)
SELECT
    sp.publish_date                          AS report_date,
    sp.source_a,
    sp.source_b,
    sp.overlap_count,
    ROUND(
        sp.overlap_count::numeric /
        LEAST(st_a.total_articles, st_b.total_articles) * 100,
        2
    )                                        AS overlap_rate,
    st_a.total_articles                      AS total_a,
    st_b.total_articles                      AS total_b
FROM source_pairs sp
JOIN source_totals st_a
    ON st_a.publish_date = sp.publish_date
    AND st_a.source_name = sp.source_a
JOIN source_totals st_b
    ON st_b.publish_date = sp.publish_date
    AND st_b.source_name = sp.source_b
ON CONFLICT (report_date, source_a, source_b)
DO UPDATE SET
    overlap_count = EXCLUDED.overlap_count,
    overlap_rate  = EXCLUDED.overlap_rate,
    total_a       = EXCLUDED.total_a,
    total_b       = EXCLUDED.total_b,
    created_at    = NOW();

CREATE INDEX IF NOT EXISTS idx_source_comparison_date
    ON mart.mart_source_comparison (report_date);