WITH source AS (
    SELECT * FROM {{ source('raw', 'raw_article_entities') }}
)

SELECT
    url_hash,
    entity,
    entity_type,
    label
FROM source
