CREATE DATABASE IF NOT EXISTS newspulse;

-- Raw articles
CREATE TABLE IF NOT EXISTS newspulse.raw_articles (
    url_hash String,
    url String,
    title String,
    content String,
    author String,
    publish_time DateTime,
    source String,
    source_domain String,
    category String,
    word_count Int32,
    keyword_count Int32,
    publish_hour Int16,
    crawl_latency_minutes Float32,
    crawled_at DateTime,
    loaded_at DateTime DEFAULT now()
) ENGINE = ReplacingMergeTree(loaded_at)
ORDER BY (url_hash);

-- Raw keywords
CREATE TABLE IF NOT EXISTS newspulse.raw_article_keywords (
    url_hash String,
    keyword String,
    score Float32,
    loaded_at DateTime DEFAULT now()
) ENGINE = MergeTree()
ORDER BY (url_hash, keyword);

-- Raw entities
CREATE TABLE IF NOT EXISTS newspulse.raw_article_entities (
    url_hash String,
    entity String,
    entity_type String,
    label String,
    loaded_at DateTime DEFAULT now()
) ENGINE = MergeTree()
ORDER BY (url_hash, entity_type, entity);

-- Raw sentiment
CREATE TABLE IF NOT EXISTS newspulse.raw_article_sentiment (
    url_hash String,
    sentiment_score Float32,
    sentiment_label String,
    loaded_at DateTime DEFAULT now()
) ENGINE = ReplacingMergeTree(loaded_at)
ORDER BY (url_hash);
