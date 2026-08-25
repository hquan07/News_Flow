-- ---- dim_source ----
CREATE TABLE IF NOT EXISTS warehouse.dim_source (
    source_id       SERIAL PRIMARY KEY,
    name            VARCHAR(100) NOT NULL UNIQUE,
    domain          VARCHAR(255),
    base_url        VARCHAR(500),
    created_at      TIMESTAMP DEFAULT NOW()
);

-- ---- dim_category ----
CREATE TABLE IF NOT EXISTS warehouse.dim_category (
    category_id     SERIAL PRIMARY KEY,
    name            VARCHAR(100) NOT NULL UNIQUE,
    parent_category VARCHAR(100),
    created_at      TIMESTAMP DEFAULT NOW()
);

-- ---- dim_time ----
CREATE TABLE IF NOT EXISTS warehouse.dim_time (
    time_id         SERIAL PRIMARY KEY,
    full_date       DATE NOT NULL UNIQUE,
    day_of_week     SMALLINT NOT NULL,  -- 1=Mon, 7=Sun (ISO)
    day_name        VARCHAR(20),
    week_of_year    SMALLINT,
    month           SMALLINT NOT NULL,
    month_name      VARCHAR(20),
    quarter         SMALLINT NOT NULL,
    year            SMALLINT NOT NULL,
    is_weekend      BOOLEAN NOT NULL DEFAULT FALSE,
    created_at      TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_dim_time_date
    ON warehouse.dim_time (full_date);
CREATE INDEX IF NOT EXISTS idx_dim_time_year_month
    ON warehouse.dim_time (year, month);

-- ---- dim_author ----
CREATE TABLE IF NOT EXISTS warehouse.dim_author (
    author_id       SERIAL PRIMARY KEY,
    name            VARCHAR(255) NOT NULL,
    source_id       INTEGER REFERENCES warehouse.dim_source(source_id),
    article_count   INTEGER DEFAULT 0,
    created_at      TIMESTAMP DEFAULT NOW(),
    updated_at      TIMESTAMP DEFAULT NOW(),

    CONSTRAINT uq_author_name_source UNIQUE (name, source_id)
);

-- ---- dim_keyword ----
CREATE TABLE IF NOT EXISTS warehouse.dim_keyword (
    keyword_id      SERIAL PRIMARY KEY,
    keyword         VARCHAR(255) NOT NULL UNIQUE,
    is_trending     BOOLEAN DEFAULT FALSE,
    first_seen_at   TIMESTAMP DEFAULT NOW(),
    last_seen_at    TIMESTAMP DEFAULT NOW(),
    total_count     INTEGER DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_dim_keyword_trending
    ON warehouse.dim_keyword (is_trending)
    WHERE is_trending = TRUE;

-- ---- dim_entity (from NER) ----
CREATE TABLE IF NOT EXISTS warehouse.dim_entity (
    entity_id       SERIAL PRIMARY KEY,
    entity_name     VARCHAR(500) NOT NULL,
    entity_type     VARCHAR(50) NOT NULL,  -- person, location, organization
    first_seen_at   TIMESTAMP DEFAULT NOW(),
    last_seen_at    TIMESTAMP DEFAULT NOW(),
    mention_count   INTEGER DEFAULT 0,

    CONSTRAINT uq_entity_name_type UNIQUE (entity_name, entity_type)
);

CREATE INDEX IF NOT EXISTS idx_dim_entity_type
    ON warehouse.dim_entity (entity_type);


-- Seed dimension data
-- Seed dim_source (matches sources.yml)
INSERT INTO warehouse.dim_source (name, domain, base_url) VALUES
    ('vnexpress', 'vnexpress.net', 'https://vnexpress.net'),
    ('tuoitre', 'tuoitre.vn', 'https://tuoitre.vn'),
    ('thanhnien', 'thanhnien.vn', 'https://thanhnien.vn')
ON CONFLICT (name) DO NOTHING;

-- Seed dim_category (all 10 categories matching Kafka topics)
INSERT INTO warehouse.dim_category (name, parent_category) VALUES
    ('sports', NULL),
    ('tech', NULL),
    ('economy', NULL),
    ('politics', NULL),
    ('general', NULL),
    ('entertainment', NULL),
    ('health', NULL),
    ('education', NULL),
    ('world', NULL),
    ('law', NULL)
ON CONFLICT (name) DO NOTHING;

-- Populate dim_time (2024-01-01 through 2026-12-31)
INSERT INTO warehouse.dim_time (
    full_date, day_of_week, day_name,
    week_of_year, month, month_name,
    quarter, year, is_weekend
)
SELECT
    d::DATE                                             AS full_date,
    EXTRACT(ISODOW FROM d)::SMALLINT                    AS day_of_week,
    TO_CHAR(d, 'Day')                                   AS day_name,
    EXTRACT(WEEK FROM d)::SMALLINT                      AS week_of_year,
    EXTRACT(MONTH FROM d)::SMALLINT                     AS month,
    TO_CHAR(d, 'Month')                                 AS month_name,
    EXTRACT(QUARTER FROM d)::SMALLINT                   AS quarter,
    EXTRACT(YEAR FROM d)::SMALLINT                      AS year,
    CASE WHEN EXTRACT(ISODOW FROM d) IN (6, 7) THEN TRUE ELSE FALSE END AS is_weekend
FROM generate_series(
    '2024-01-01'::DATE,
    '2026-12-31'::DATE,
    '1 day'::INTERVAL
) AS d
ON CONFLICT (full_date) DO NOTHING;