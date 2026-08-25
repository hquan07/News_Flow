-- ---- Fact: fact_article ----
CREATE TABLE IF NOT EXISTS warehouse.fact_article (
    article_id      BIGSERIAL PRIMARY KEY,
    url_hash        VARCHAR(64) NOT NULL UNIQUE,
    source_id       INTEGER NOT NULL REFERENCES warehouse.dim_source(source_id),
    category_id     INTEGER NOT NULL REFERENCES warehouse.dim_category(category_id),
    time_id         INTEGER REFERENCES warehouse.dim_time(time_id),
    author_id       INTEGER REFERENCES warehouse.dim_author(author_id),

    -- Measures
    word_count          INTEGER DEFAULT 0,
    keyword_count       INTEGER DEFAULT 0,
    publish_hour        SMALLINT,
    crawl_latency_minutes NUMERIC(10, 1),
    person_count        INTEGER DEFAULT 0,
    location_count      INTEGER DEFAULT 0,
    org_count           INTEGER DEFAULT 0,

    -- Metadata
    url             TEXT NOT NULL,
    title           TEXT NOT NULL,
    publish_time    TIMESTAMP,
    sentiment_score NUMERIC(5, 4),
    sentiment_label VARCHAR(20),
    created_at      TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_fact_article_source
    ON warehouse.fact_article (source_id);
CREATE INDEX IF NOT EXISTS idx_fact_article_category
    ON warehouse.fact_article (category_id);
CREATE INDEX IF NOT EXISTS idx_fact_article_time
    ON warehouse.fact_article (time_id);
CREATE INDEX IF NOT EXISTS idx_fact_article_publish_time
    ON warehouse.fact_article (publish_time);

-- ---- Bridge: bridge_article_keyword ----
CREATE TABLE IF NOT EXISTS warehouse.bridge_article_keyword (
    article_id      BIGINT NOT NULL REFERENCES warehouse.fact_article(article_id),
    keyword_id      INTEGER NOT NULL REFERENCES warehouse.dim_keyword(keyword_id),
    relevance_score NUMERIC(6, 4),

    PRIMARY KEY (article_id, keyword_id)
);

-- ---- Bridge: bridge_article_entity ----
CREATE TABLE IF NOT EXISTS warehouse.bridge_article_entity (
    article_id      BIGINT NOT NULL REFERENCES warehouse.fact_article(article_id),
    entity_id       INTEGER NOT NULL REFERENCES warehouse.dim_entity(entity_id),

    PRIMARY KEY (article_id, entity_id)
);