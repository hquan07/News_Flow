# NewsPulse

**Realtime News Intelligence Platform**

A real-time news analysis platform that collects and processes articles from Vietnam's three largest online newspapers. The system runs entirely on-premise without cloud dependencies.

---

## Key Features

- **Automated Crawling** from VnExpress, Tuổi Trẻ, and Thanh Niên via Scrapy crawlers
- **Streaming Pipeline** with Kafka → Spark Structured Streaming
- **Vietnamese NLP** — keyword extraction, Named Entity Recognition (PER/LOC/ORG), and sentiment analysis using `underthesea`
- **Data Warehouse** structured as a star schema on PostgreSQL (raw → staging → warehouse → mart)
- **REST API** powered by FastAPI serving analytics endpoints
- **Custom Dashboard** for real-time visualization — tracking trends, source comparisons, entity networks, and volume spikes
- **Monitoring** — Docker healthchecks, Airflow DAGs, and data quality validation (39 checks)
- **100% Containerized** — a single `docker compose up -d` brings up the entire infrastructure

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Crawling | Python, Scrapy, BeautifulSoup4, feedparser |
| Message Broker | Apache Kafka (category-based topics) |
| Stream Processing | Apache Spark Structured Streaming |
| Raw Storage | MongoDB |
| Data Warehouse | PostgreSQL (star schema, 4 schema layers) |
| NLP | underthesea (Vietnamese NER, Sentiment Analysis) |
| Orchestration | Apache Airflow |
| API | FastAPI |
| Dashboard | Vanilla JS, HTML, CSS, Chart.js, Vis.js |
| Monitoring | Docker healthchecks, loguru, Great Expectations |
| Infrastructure | Docker, Docker Compose |

## Architecture

```text
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│  VnExpress  │     │  Tuổi Trẻ   │     │  Thanh Niên  │
└──────┬──────┘     └──────┬──────┘     └──────┬──────┘
       │                   │                   │
       └───────────┬───────┴───────────────────┘
                   │
          ┌────────▼────────┐
          │ Scrapy Crawlers │  ← Airflow scheduled
          └────────┬────────┘
                   │
          ┌────────▼────────┐
          │   Apache Kafka  │
          └────────┬────────┘
                   │
       ┌───────────┼───────────┐
       │                       │
┌──────▼──────┐       ┌───────▼────────┐
│   MongoDB   │       │ Spark Streaming│
│  (raw JSON) │       │ + NLP Pipeline │
└─────────────┘       └───────┬────────┘
                              │
                    ┌─────────▼─────────┐
                    │    PostgreSQL     │
                    │  raw → staging →  │
                    │ warehouse → mart  │
                    └─────────┬─────────┘
                              │
                 ┌────────────┼────────────┐
                 │            │            │
          ┌──────▼───┐  ┌────▼────┐  ┌────▼─────┐
          │ FastAPI  │  │ Vanilla │  │ Airflow  │
          │ REST API │  │Dashboard│  │   UI     │
          └──────────┘  └─────────┘  └──────────┘
```

For detailed architecture diagrams, refer to [docs/architecture.mermaid](docs/architecture.mermaid).

## Installation & Setup

### Requirements

- Docker Engine ≥ 24.0
- Docker Compose ≥ 2.20
- RAM ≥ 8GB (16GB recommended)
- Disk ≥ 20GB

### Quick Start

**1. Clone repository**
```bash
git clone https://github.com/hquan07/News_Flow.git
cd News_Flow
```

**2. Setup Environment Variables**

Before running the application, you need to configure the environment variables. The project provides an `.env.example` file which contains the required variable structure without any sensitive passwords.

**Important:** Never commit your actual `.env` file containing real passwords to GitHub. The `.env` file is already securely added to `.gitignore`.

```bash
# Copy the example file to create your local .env file
cp .env.example .env

# Open the .env file and fill in your desired secure passwords
# For example, using nano:
nano .env
```

Ensure you set secure values for variables like `PG_PASSWORD`, `MONGO_INITDB_ROOT_PASSWORD`, and `AIRFLOW__WEBSERVER__SECRET_KEY` inside your local `.env`.

**3. Start the Infrastructure**
```bash
docker compose -f docker/docker-compose.yml up -d
docker compose -f docker/docker-compose.spark.yml up -d
```

**4. Check Services**
```bash
docker compose -f docker/docker-compose.yml ps
```

**5. Access Points**
- **Airflow UI:**  `http://localhost:8080` (admin/admin by default)
- **FastAPI Docs:** `http://localhost:8001/docs`
- **Dashboard:** `http://localhost:8001/dashboard`
- **Spark Master UI:** `http://localhost:8082`

### System Checks

```bash
# Health check all services
python monitoring/health_monitor.py

# Data quality validation
python data_quality/run_validations.py

# Query benchmark
python performance/benchmark.py
```

## Data Model

### Star Schema (Warehouse Layer)

```text
                    ┌──────────────┐
                    │  dim_source  │
                    │──────────────│
                    │ source_id PK │───┐
                    │ name         │   │
                    │ domain       │   │
                    └──────────────┘   │
                                       │
┌──────────────┐   ┌─────────────────────────────────┐   ┌───────────────┐
│ dim_category │   │         fact_article            │   │   dim_time    │
│──────────────│   │─────────────────────────────────│   │───────────────│
│ category_id  │───│ article_id PK                   │───│ time_id PK    │
│ name         │   │ source_id FK    → dim_source    │   │ full_date     │
│ parent       │   │ category_id FK  → dim_category  │   │ day_of_week   │
└──────────────┘   │ time_id FK      → dim_time      │   │ month, quarter│
                   │ author_id FK    → dim_author    │   │ is_weekend    │
┌──────────────┐   │                                 │   └───────────────┘
│  dim_author  │   │ word_count, keyword_count       │
│──────────────│   │ publish_hour                    │   ┌───────────────┐
│ author_id PK │───│ crawl_latency_minutes           │   │  dim_keyword  │
│ name         │   │ person_count, location_count    │   │───────────────│
│ source_id FK │   │ org_count                       │   │ keyword_id PK │
└──────────────┘   │ sentiment_score, sentiment_label│   │ keyword       │
                   └──────────┬──────────┬───────────┘   │ is_trending   │
                              │          │               └───────┬───────┘
                   ┌──────────▼───┐  ┌───▼────────────┐          │
                   │bridge_article│  │bridge_article  │──────────┘
                   │   _entity    │  │   _keyword     │
                   │──────────────│  │────────────────│
                   │ article_id   │  │ article_id     │
                   │ entity_id    │  │ keyword_id     │
                   └──────┬───────┘  │ relevance_score│
                          │          └────────────────┘
                   ┌──────▼───────┐
                   │  dim_entity  │
                   │──────────────│
                   │ entity_id PK │
                   │ entity       │
                   │ entity_type  │  (PER/LOC/ORG)
                   │ mention_count│
                   └──────────────┘
```

### Schema Layers

| Layer | Schema | Purpose |
|-------|--------|---------|
| Raw | `raw` | Data arriving directly from Spark/MongoDB, retaining original structure |
| Staging | `staging` | Cleaned, deduplicated, and type-normalized data |
| Warehouse | `warehouse` | Analytical Star schema (fact + dimensions + bridges) |
| Mart | `mart` | Pre-aggregated tables and materialized views optimized for the dashboard |

## Dashboard

The custom HTML/JS dashboard includes 4 primary views:

| Page | Content |
|-------|---------|
| **Overview** | KPI cards, articles by hour, category distribution, sentiment breakdown, average crawl latency |
| **Trending** | Top trending keywords, temporal trends, and keyword co-occurrences |
| **Sources** | Source composition by category and article ingestion speed |
| **Entities** | People, Locations, and Organizations tracking, alongside a dynamic Entity Co-occurrence Network Graph |

## Monitoring

| Component | Description |
|-----------|-------------|
| Docker Healthchecks | Integrated health checks for all services (Kafka, MongoDB, PostgreSQL, Airflow, API) |
| `/health/detailed` | FastAPI endpoint for deep-checking the entire service mesh |
| `health_monitor.py` | CLI tool for system validation returning standard exit codes (0/1) |
| `dag_health_check` | Airflow DAG running every 15 mins to check service health, data freshness, and Kafka lag |
| `dag_data_quality` | 39 automated SQL validation tests across the 3 main data layers |

## Performance Tuning

Key optimizations applied:
- **PostgreSQL**: Implemented 13 composite indexes, 3 materialized views, and tuned config variables specifically for SSD-based workloads.
- **Spark Streaming**: Enabled Adaptive Query Execution (AQE), matched shuffle partitions to logical parallelism, used Kryo serialization, and G1GC.
- **Benchmarks**: Benchmarked with `performance/benchmark.py` showing significant sub-second query improvements across all dashboard endpoints.

## Implementation Phases

| Phase | Details |
|-------|---------|
| 1 | Foundation & Data Ingestion (Scrapy, Kafka, MongoDB) |
| 2 | Processing & Data Warehouse (Spark Structured Streaming, PostgreSQL star schema, ELT) |
| 3 | Serving & Visualization (FastAPI backend, Vanilla JS Custom Dashboard) |
| 4 | Optimization & Ops (Monitoring, Data Quality Checks, Performance Tuning, Documentation) |

## License

MIT

## Author

**Quan** — [GitHub](https://github.com/hquan07)