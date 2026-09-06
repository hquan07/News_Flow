CREATE SCHEMA IF NOT EXISTS mart;

DROP TABLE IF EXISTS mart.mart_hourly_distribution;

CREATE TABLE mart.mart_hourly_distribution (
    id              SERIAL PRIMARY KEY,
    report_date     DATE NOT NULL,
    source_name     VARCHAR(100) NOT NULL,
    hour            SMALLINT NOT NULL CHECK (hour >= 0 AND hour <= 23),
    article_count   INTEGER NOT NULL DEFAULT 0,
    created_at      TIMESTAMP DEFAULT NOW(),

    UNIQUE (report_date, source_name, hour)
);

-- Populate
INSERT INTO mart.mart_hourly_distribution (
    report_date, source_name, hour, article_count
)
SELECT
    dt.date              AS report_date,
    ds.name              AS source_name,
    fa.publish_hour      AS hour,
    COUNT(*)             AS article_count
FROM warehouse.fact_article fa
JOIN warehouse.dim_source ds ON fa.source_id = ds.source_id
JOIN warehouse.dim_time dt ON fa.time_id = dt.time_id
GROUP BY dt.date, ds.name, fa.publish_hour
ON CONFLICT (report_date, source_name, hour)
DO UPDATE SET
    article_count = EXCLUDED.article_count,
    created_at    = NOW();

CREATE INDEX IF NOT EXISTS idx_hourly_dist_date
    ON mart.mart_hourly_distribution (report_date);

CREATE INDEX IF NOT EXISTS idx_hourly_dist_hour
    ON mart.mart_hourly_distribution (hour);