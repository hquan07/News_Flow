WITH source AS (
    SELECT * FROM {{ source('raw', 'raw_article_sentiment') }}
)

SELECT
    url_hash,
    sentiment_score,
    sentiment_label
FROM source
