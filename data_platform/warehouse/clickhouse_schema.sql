CREATE DATABASE IF NOT EXISTS newspulse;

-- Raw articles
CREATE TABLE IF NOT EXISTS newspulse.raw_articles (
    url_hash String,
    event_id String DEFAULT '',
    kafka_topic String DEFAULT '',
    kafka_partition Int32 DEFAULT -1,
    kafka_offset Int64 DEFAULT -1,
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
    clickbait_score Float32 DEFAULT 0.0,
    crawled_at DateTime,
    loaded_at DateTime DEFAULT now()
) ENGINE = ReplacingMergeTree(loaded_at)
ORDER BY (url_hash)
SETTINGS non_replicated_deduplication_window = 10000;

ALTER TABLE newspulse.raw_articles ADD COLUMN IF NOT EXISTS event_id String DEFAULT '';
ALTER TABLE newspulse.raw_articles ADD COLUMN IF NOT EXISTS kafka_topic String DEFAULT '';
ALTER TABLE newspulse.raw_articles ADD COLUMN IF NOT EXISTS kafka_partition Int32 DEFAULT -1;
ALTER TABLE newspulse.raw_articles ADD COLUMN IF NOT EXISTS kafka_offset Int64 DEFAULT -1;
ALTER TABLE newspulse.raw_articles MODIFY SETTING non_replicated_deduplication_window = 10000;

-- Raw keywords
CREATE TABLE IF NOT EXISTS newspulse.raw_article_keywords (
    url_hash String,
    keyword String,
    score Float32,
    loaded_at DateTime DEFAULT now()
) ENGINE = MergeTree()
ORDER BY (url_hash, keyword)
SETTINGS non_replicated_deduplication_window = 10000;
ALTER TABLE newspulse.raw_article_keywords MODIFY SETTING non_replicated_deduplication_window = 10000;

-- Raw entities
CREATE TABLE IF NOT EXISTS newspulse.raw_article_entities (
    url_hash String,
    entity String,
    entity_type String,
    label String,
    loaded_at DateTime DEFAULT now()
) ENGINE = MergeTree()
ORDER BY (url_hash, entity_type, entity)
SETTINGS non_replicated_deduplication_window = 10000;
ALTER TABLE newspulse.raw_article_entities MODIFY SETTING non_replicated_deduplication_window = 10000;

-- Raw sentiment
CREATE TABLE IF NOT EXISTS newspulse.raw_article_sentiment (
    url_hash String,
    sentiment_score Float32,
    sentiment_label String,
    loaded_at DateTime DEFAULT now()
) ENGINE = ReplacingMergeTree(loaded_at)
ORDER BY (url_hash)
SETTINGS non_replicated_deduplication_window = 10000;
ALTER TABLE newspulse.raw_article_sentiment MODIFY SETTING non_replicated_deduplication_window = 10000;

-- Clickbait enrichment is stored separately so raw ingestion never waits for an LLM.
CREATE TABLE IF NOT EXISTS newspulse.raw_article_clickbait (
    url_hash String,
    clickbait_score Float32,
    processed_at DateTime DEFAULT now()
) ENGINE = ReplacingMergeTree(processed_at)
ORDER BY (url_hash)
SETTINGS non_replicated_deduplication_window = 10000;
ALTER TABLE newspulse.raw_article_clickbait MODIFY SETTING non_replicated_deduplication_window = 10000;

-- Raw AI Summaries (Groq LLM)
CREATE TABLE IF NOT EXISTS newspulse.raw_article_summaries (
    url_hash String,
    summary String,
    model_name String,
    processed_at DateTime DEFAULT now()
) ENGINE = ReplacingMergeTree(processed_at)
ORDER BY (url_hash);

-- Raw AI Embeddings (Sentence Transformers)
CREATE TABLE IF NOT EXISTS newspulse.raw_article_embeddings (
    url_hash String,
    embedding Array(Float32),
    model_name String,
    processed_at DateTime DEFAULT now()
) ENGINE = ReplacingMergeTree(processed_at)
ORDER BY (url_hash);

-- Social Sentiment Metrics (Mạng xã hội)
CREATE TABLE IF NOT EXISTS newspulse.social_sentiment_metrics (
    post_id String,
    url String DEFAULT '',
    author String DEFAULT '',
    top_comments Array(String) DEFAULT [],
    kafka_topic String DEFAULT '',
    kafka_partition Int32 DEFAULT -1,
    kafka_offset Int64 DEFAULT -1,
    source String,
    title String,
    content String,
    like_count Int32,
    upvote_ratio Float32,
    reply_count Int32,
    sentiment_score Float32,
    sentiment_label String,
    publish_time DateTime,
    crawled_at DateTime DEFAULT now(),
    loaded_at DateTime DEFAULT now()
) ENGINE = ReplacingMergeTree(loaded_at)
PARTITION BY toYYYYMM(publish_time)
ORDER BY (source, publish_time, post_id)
SETTINGS non_replicated_deduplication_window = 10000;

ALTER TABLE newspulse.social_sentiment_metrics ADD COLUMN IF NOT EXISTS url String DEFAULT '';
ALTER TABLE newspulse.social_sentiment_metrics ADD COLUMN IF NOT EXISTS author String DEFAULT '';
ALTER TABLE newspulse.social_sentiment_metrics ADD COLUMN IF NOT EXISTS top_comments Array(String) DEFAULT [];
ALTER TABLE newspulse.social_sentiment_metrics ADD COLUMN IF NOT EXISTS kafka_topic String DEFAULT '';
ALTER TABLE newspulse.social_sentiment_metrics ADD COLUMN IF NOT EXISTS kafka_partition Int32 DEFAULT -1;
ALTER TABLE newspulse.social_sentiment_metrics ADD COLUMN IF NOT EXISTS kafka_offset Int64 DEFAULT -1;
ALTER TABLE newspulse.social_sentiment_metrics MODIFY SETTING non_replicated_deduplication_window = 10000;

-- Event Clusters (Topic Modeling)
CREATE TABLE IF NOT EXISTS newspulse.event_clusters (
    cluster_id String,
    cluster_name String,
    top_keywords Array(String),
    article_count Int32,
    avg_sentiment Float32,
    start_time DateTime,
    end_time DateTime,
    created_at DateTime DEFAULT now()
) ENGINE = ReplacingMergeTree(created_at)
ORDER BY (start_time, cluster_id);

-- User Interactions (Personalization)
CREATE TABLE IF NOT EXISTS newspulse.user_interactions (
    user_id String,
    article_hash String,
    interaction_type String, -- 'click', 'like', 'share', 'read_complete'
    interaction_weight Float32 DEFAULT 1.0,
    timestamp DateTime DEFAULT now()
) ENGINE = MergeTree()
PARTITION BY toYYYYMM(timestamp)
ORDER BY (user_id, timestamp, article_hash);
