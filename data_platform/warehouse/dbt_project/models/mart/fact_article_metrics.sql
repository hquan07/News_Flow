WITH articles AS (
    SELECT * FROM {{ ref('stg_articles') }}
),
sentiment AS (
    SELECT * FROM {{ ref('stg_sentiment') }}
),
entities AS (
    SELECT
        url_hash,
        count(case when entity_type = 'person' then 1 end) as person_count,
        count(case when entity_type = 'location' then 1 end) as location_count,
        count(case when entity_type = 'organization' then 1 end) as org_count
    FROM {{ ref('stg_entities') }}
    GROUP BY url_hash
)

SELECT
    a.url_hash,
    a.url,
    a.title,
    a.author,
    a.source,
    a.category,
    a.publish_time,
    a.crawled_at,
    COALESCE(s.sentiment_score, 0) AS sentiment_score,
    COALESCE(s.sentiment_label, 'neutral') AS sentiment_label,
    COALESCE(e.person_count, 0) AS person_count,
    COALESCE(e.location_count, 0) AS location_count,
    COALESCE(e.org_count, 0) AS org_count
FROM articles a
LEFT JOIN sentiment s ON a.url_hash = s.url_hash
LEFT JOIN entities e ON a.url_hash = e.url_hash
