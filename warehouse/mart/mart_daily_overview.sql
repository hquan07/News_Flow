CREATE SCHEMA IF NOT EXISTS mart;

DROP TABLE IF EXISTS mart.mart_daily_overview;

CREATE TABLE mart.mart_daily_overview (
    id              SERIAL PRIMARY KEY,
    report_date     DATE NOT NULL,
    source_name     VARCHAR(100) NOT NULL,
    category_name   VARCHAR(100) NOT NULL,
    article_count   INTEGER NOT NULL DEFAULT 0,
    avg_word_count  NUMERIC(10, 1),
    avg_keyword_count NUMERIC(10, 1),
    created_at      TIMESTAMP DEFAULT NOW(),

    UNIQUE (report_date, source_name, category_name)
);

-- Populate / refresh
INSERT INTO mart.mart_daily_overview (
    report_date, source_name, category_name,
    article_count, avg_word_count, avg_keyword_count
)
SELECT
    dt.date                          AS report_date,
    ds.name                          AS source_name,
    dc.name                          AS category_name,
    COUNT(*)                         AS article_count,
    ROUND(AVG(fa.word_count), 1)     AS avg_word_count,
    ROUND(AVG(fa.keyword_count), 1)  AS avg_keyword_count
FROM warehouse.fact_article fa
JOIN warehouse.dim_source   ds ON fa.source_id   = ds.source_id
JOIN warehouse.dim_category dc ON fa.category_id = dc.category_id
JOIN warehouse.dim_time     dt ON fa.time_id     = dt.time_id
GROUP BY dt.date, ds.name, dc.name
ON CONFLICT (report_date, source_name, category_name)
DO UPDATE SET
    article_count     = EXCLUDED.article_count,
    avg_word_count    = EXCLUDED.avg_word_count,
    avg_keyword_count = EXCLUDED.avg_keyword_count,
    created_at        = NOW();

-- Index for time-range queries
CREATE INDEX IF NOT EXISTS idx_daily_overview_date
    ON mart.mart_daily_overview (report_date);

CREATE INDEX IF NOT EXISTS idx_daily_overview_source
    ON mart.mart_daily_overview (source_name, report_date);