-- 3. STAGING LAYER
-- Cleaned, deduped, type-normalized data.
-- Ready for loading into the star schema.
CREATE TABLE IF NOT EXISTS staging.articles (
    id              BIGSERIAL PRIMARY KEY,
    url             TEXT NOT NULL,
    url_hash        VARCHAR(64) NOT NULL UNIQUE,
    title           TEXT NOT NULL,
    content         TEXT,
    author          VARCHAR(255),
    publish_time    TIMESTAMP,
    source          VARCHAR(100) NOT NULL,
    source_domain   VARCHAR(255),
    category        VARCHAR(100) NOT NULL,
    word_count      INTEGER DEFAULT 0,
    keyword_count   INTEGER DEFAULT 0,
    publish_hour    SMALLINT,
    crawl_latency_minutes NUMERIC(10, 1),
    crawled_at      TIMESTAMP,
    sentiment_score NUMERIC(5, 4),
    sentiment_label VARCHAR(20),
    loaded_at       TIMESTAMP DEFAULT NOW(),
    staged_at       TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_staging_articles_source
    ON staging.articles (source);
CREATE INDEX IF NOT EXISTS idx_staging_articles_category
    ON staging.articles (category);
CREATE INDEX IF NOT EXISTS idx_staging_articles_publish_time
    ON staging.articles (publish_time);