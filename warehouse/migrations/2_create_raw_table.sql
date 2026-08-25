-- Flat data loaded directly from Spark/MongoDB.
-- Preserves original structure, minimal transformation.
CREATE TABLE IF NOT EXISTS raw.articles (
    id              BIGSERIAL PRIMARY KEY,
    url             TEXT NOT NULL,
    url_hash        VARCHAR(64),
    title           TEXT NOT NULL,
    content         TEXT,
    author          VARCHAR(255),
    publish_time    TIMESTAMP,
    source          VARCHAR(100),
    source_domain   VARCHAR(255),
    category        VARCHAR(100),
    word_count      INTEGER,
    keyword_count   INTEGER,
    publish_hour    SMALLINT,
    crawl_latency_minutes NUMERIC(10, 1),
    crawled_at      TIMESTAMP,
    loaded_at       TIMESTAMP DEFAULT NOW(),

    CONSTRAINT uq_raw_url_hash UNIQUE (url_hash)
);

CREATE INDEX IF NOT EXISTS idx_raw_articles_source
    ON raw.articles (source);
CREATE INDEX IF NOT EXISTS idx_raw_articles_publish_time
    ON raw.articles (publish_time);
CREATE INDEX IF NOT EXISTS idx_raw_articles_category
    ON raw.articles (category);

-- Raw keywords table (one row per article-keyword pair)
CREATE TABLE IF NOT EXISTS raw.article_keywords (
    id              BIGSERIAL PRIMARY KEY,
    url_hash        VARCHAR(64) NOT NULL,
    keyword         VARCHAR(255) NOT NULL,
    score           NUMERIC(6, 4),
    loaded_at       TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_raw_keywords_url_hash
    ON raw.article_keywords (url_hash);

-- Raw entities table (one row per article-entity pair)
CREATE TABLE IF NOT EXISTS raw.article_entities (
    id              BIGSERIAL PRIMARY KEY,
    url_hash        VARCHAR(64) NOT NULL,
    entity          VARCHAR(500) NOT NULL,
    entity_type     VARCHAR(50) NOT NULL,  -- person, location, organization
    label           VARCHAR(10),
    loaded_at       TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_raw_entities_url_hash
    ON raw.article_entities (url_hash);
CREATE INDEX IF NOT EXISTS idx_raw_entities_type
    ON raw.article_entities (entity_type);

-- Raw sentiment table (one row per article)
CREATE TABLE IF NOT EXISTS raw.article_sentiment (
    id              BIGSERIAL PRIMARY KEY,
    url_hash        VARCHAR(64) NOT NULL,
    sentiment_score NUMERIC(5, 4),
    sentiment_label VARCHAR(20),
    loaded_at       TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_raw_sentiment_url_hash
    ON raw.article_sentiment (url_hash);