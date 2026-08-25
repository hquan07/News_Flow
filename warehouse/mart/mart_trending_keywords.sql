CREATE SCHEMA IF NOT EXISTS mart;

DROP TABLE IF EXISTS mart.mart_trending_keywords;

CREATE TABLE mart.mart_trending_keywords (
    id              SERIAL PRIMARY KEY,
    keyword         VARCHAR(255) NOT NULL,
    total_count     INTEGER NOT NULL DEFAULT 0,
    trend           VARCHAR(10) DEFAULT 'stable',  -- up / down / stable
    sparkline_data  JSONB DEFAULT '[]'::jsonb,
    period_start    DATE NOT NULL,
    period_end      DATE NOT NULL,
    created_at      TIMESTAMP DEFAULT NOW(),

    UNIQUE (keyword, period_start, period_end)
);

-- Populate: last 7 days, top 100 keywords
INSERT INTO mart.mart_trending_keywords (
    keyword, total_count, trend, sparkline_data,
    period_start, period_end
)
WITH keyword_counts AS (
    SELECT
        dk.keyword,
        COUNT(*) AS total_count
    FROM warehouse.bridge_article_keyword bak
    JOIN warehouse.dim_keyword dk ON bak.keyword_id = dk.keyword_id
    JOIN warehouse.fact_article fa ON bak.article_id = fa.article_id
    JOIN warehouse.dim_time dt ON fa.time_id = dt.time_id
    WHERE dt.date >= CURRENT_DATE - INTERVAL '7 days'
    GROUP BY dk.keyword
    ORDER BY total_count DESC
    LIMIT 100
),
-- Sparkline: daily counts for each keyword over 7 days
sparkline AS (
    SELECT
        dk.keyword,
        JSONB_AGG(
            COALESCE(daily.cnt, 0) ORDER BY d.date
        ) AS sparkline_data
    FROM keyword_counts kc
    JOIN warehouse.dim_keyword dk ON dk.keyword = kc.keyword
    CROSS JOIN (
        SELECT generate_series(
            CURRENT_DATE - INTERVAL '6 days',
            CURRENT_DATE,
            '1 day'::interval
        )::date AS date
    ) d
    LEFT JOIN (
        SELECT
            dk2.keyword,
            dt.date,
            COUNT(*) AS cnt
        FROM warehouse.bridge_article_keyword bak
        JOIN warehouse.dim_keyword dk2 ON bak.keyword_id = dk2.keyword_id
        JOIN warehouse.fact_article fa ON bak.article_id = fa.article_id
        JOIN warehouse.dim_time dt ON fa.time_id = dt.time_id
        WHERE dt.date >= CURRENT_DATE - INTERVAL '7 days'
        GROUP BY dk2.keyword, dt.date
    ) daily ON daily.keyword = dk.keyword AND daily.date = d.date
    GROUP BY dk.keyword
),
-- Trend detection: compare last 3 days vs prior 4 days
trend_calc AS (
    SELECT
        dk.keyword,
        SUM(CASE WHEN dt.date >= CURRENT_DATE - INTERVAL '3 days'
                 THEN 1 ELSE 0 END) AS recent_count,
        SUM(CASE WHEN dt.date < CURRENT_DATE - INTERVAL '3 days'
                 THEN 1 ELSE 0 END) AS prior_count
    FROM warehouse.bridge_article_keyword bak
    JOIN warehouse.dim_keyword dk ON bak.keyword_id = dk.keyword_id
    JOIN warehouse.fact_article fa ON bak.article_id = fa.article_id
    JOIN warehouse.dim_time dt ON fa.time_id = dt.time_id
    WHERE dt.date >= CURRENT_DATE - INTERVAL '7 days'
      AND dk.keyword IN (SELECT keyword FROM keyword_counts)
    GROUP BY dk.keyword
)
SELECT
    kc.keyword,
    kc.total_count,
    CASE
        WHEN tc.recent_count > tc.prior_count * 1.3 THEN 'up'
        WHEN tc.recent_count < tc.prior_count * 0.7 THEN 'down'
        ELSE 'stable'
    END AS trend,
    COALESCE(sp.sparkline_data, '[]'::jsonb) AS sparkline_data,
    CURRENT_DATE - INTERVAL '7 days' AS period_start,
    CURRENT_DATE AS period_end
FROM keyword_counts kc
LEFT JOIN sparkline sp ON sp.keyword = kc.keyword
LEFT JOIN trend_calc tc ON tc.keyword = kc.keyword
ON CONFLICT (keyword, period_start, period_end)
DO UPDATE SET
    total_count    = EXCLUDED.total_count,
    trend          = EXCLUDED.trend,
    sparkline_data = EXCLUDED.sparkline_data,
    created_at     = NOW();

CREATE INDEX IF NOT EXISTS idx_trending_keywords_period
    ON mart.mart_trending_keywords (period_start, period_end);

CREATE INDEX IF NOT EXISTS idx_trending_keywords_count
    ON mart.mart_trending_keywords (total_count DESC);