WITH source AS (
    SELECT * FROM {{ source('raw', 'raw_articles') }}
)

SELECT
    url_hash,
    url,
    title,
    content,
    author,
    publish_time,
    source,
    source_domain,
    category,
    word_count,
    keyword_count,
    publish_hour,
    crawl_latency_minutes,
    crawled_at
FROM source
