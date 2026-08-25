-- mart.daily_overview
CREATE TABLE IF NOT EXISTS mart.daily_overview (
    date            DATE NOT NULL,
    source          VARCHAR(100) NOT NULL,
    category        VARCHAR(100) NOT NULL,
    article_count   INTEGER DEFAULT 0,
    avg_word_count  NUMERIC(10, 1),
    avg_crawl_latency NUMERIC(10, 1),
    PRIMARY KEY (date, source, category)
);

-- mart.hourly_distribution
CREATE TABLE IF NOT EXISTS mart.hourly_distribution (
    date            DATE NOT NULL,
    hour            SMALLINT NOT NULL,
    source          VARCHAR(100) NOT NULL,
    article_count   INTEGER DEFAULT 0,
    PRIMARY KEY (date, hour, source)
);

-- mart.trending_keywords
CREATE TABLE IF NOT EXISTS mart.trending_keywords (
    week_start      DATE NOT NULL,
    keyword         VARCHAR(255) NOT NULL,
    mention_count   INTEGER DEFAULT 0,
    prev_week_count INTEGER DEFAULT 0,
    spike_score     NUMERIC(10, 2),
    PRIMARY KEY (week_start, keyword)
);

-- mart.source_comparison
CREATE TABLE IF NOT EXISTS mart.source_comparison (
    date            DATE NOT NULL,
    source          VARCHAR(100) NOT NULL,
    total_articles  INTEGER DEFAULT 0,
    avg_publish_hour NUMERIC(4, 1),
    top_category    VARCHAR(100),
    avg_word_count  NUMERIC(10, 1),
    PRIMARY KEY (date, source)
);

-- mart.entity_trending (NER)
CREATE TABLE IF NOT EXISTS mart.entity_trending (
    date            DATE NOT NULL,
    entity          VARCHAR(500) NOT NULL,
    entity_type     VARCHAR(50) NOT NULL,
    mention_count   INTEGER DEFAULT 0,
    article_count   INTEGER DEFAULT 0,
    PRIMARY KEY (date, entity, entity_type)
);

-- mart.entity_network
CREATE TABLE IF NOT EXISTS mart.entity_network (
    date            DATE NOT NULL,
    entity_a        VARCHAR(500) NOT NULL,
    entity_b        VARCHAR(500) NOT NULL,
    co_occurrence_count INTEGER DEFAULT 0,
    PRIMARY KEY (date, entity_a, entity_b)
);
