#!/usr/bin/env bash
# ============================================================================
# NewsPulse — Master Startup Script
# ============================================================================
# Usage:
#   chmod +x start.sh
#   ./start.sh              # Chạy toàn bộ
#   ./start.sh --phase 1    # Chỉ chạy Phase 1
#   ./start.sh --skip-crawl # Bỏ qua crawl (dùng khi đã có data)
#   ./start.sh --reset      # Xóa toàn bộ data, chạy lại từ đầu
# ============================================================================

# ── Colors ──
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

# ── Config ──
PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
COMPOSE="docker compose -f $PROJECT_DIR/infrastructure/docker/docker-compose.yml"

# Load .env if exists (same as docker compose does)
if [ -f "$PROJECT_DIR/.env" ]; then
    set -a
    source "$PROJECT_DIR/.env"
    set +a
fi

# PostgreSQL credentials (from .env or defaults matching docker-compose.yml)
PG_USER="${PG_USER:-newspulse}"
PG_PASSWORD="${PG_PASSWORD:-newspulse}"
PG_DB="${PG_DB:-newspulse}"

# ── Args ──
PHASE=""
SKIP_CRAWL=false
RESET=false

while [[ $# -gt 0 ]]; do
    case $1 in
        --phase)     PHASE="$2"; shift 2 ;;
        --skip-crawl) SKIP_CRAWL=true; shift ;;
        --reset)     RESET=true; shift ;;
        -h|--help)
            echo "Usage: ./start.sh [--phase N] [--skip-crawl] [--reset]"
            exit 0 ;;
        *) echo "Unknown option: $1"; exit 1 ;;
    esac
done

# ── Helpers ──
log()    { echo -e "${BLUE}[$(date '+%H:%M:%S')]${NC} $1"; }
ok()     { echo -e "${GREEN}[$(date '+%H:%M:%S')] ✅ $1${NC}"; }
warn()   { echo -e "${YELLOW}[$(date '+%H:%M:%S')] ⚠️  $1${NC}"; }
fail()   { echo -e "${RED}[$(date '+%H:%M:%S')] ❌ $1${NC}"; exit 1; }
header() { echo -e "\n${CYAN}══════════════════════════════════════════════════════════${NC}"; echo -e "${CYAN}  $1${NC}"; echo -e "${CYAN}══════════════════════════════════════════════════════════${NC}\n"; }

# Get container ID for a service
get_cid() {
    $COMPOSE ps -q "$1" 2>/dev/null | head -1
}

# Run command inside a container with 15s timeout
# Uses docker exec directly (docker compose exec hangs in subshells)
dc_exec() {
    local svc="$1"; shift
    local cid
    cid=$(get_cid "$svc")
    if [ -z "$cid" ]; then
        return 1
    fi
    timeout 15 docker exec "$cid" "$@" 2>/dev/null
}

# Run psql command and return clean single-line result
dc_psql() {
    local cid
    cid=$(get_cid postgres)
    if [ -z "$cid" ]; then
        echo "0"
        return 1
    fi
    timeout 15 docker exec "$cid" \
        psql -U "$PG_USER" -d "$PG_DB" -t -A -c "$1" 2>/dev/null | head -1 | tr -d '[:space:]'
}

# Check if a service exists in docker-compose.yml
has_service() {
    $COMPOSE config --services 2>/dev/null | grep -q "^${1}$"
}

# Wait for container to be healthy via docker inspect
wait_healthy() {
    local service=$1
    local max=${2:-180}
    local elapsed=0
    local crash_count=0

    log "Waiting for $service to be healthy..."
    while [ $elapsed -lt $max ]; do
        local cid
        # Use -a to also see stopped/exited containers
        cid=$($COMPOSE ps -a -q "$service" 2>/dev/null | head -1)

        if [ -z "$cid" ]; then
            # No container at all
            crash_count=$((crash_count + 1))
            if [ $crash_count -ge 3 ]; then
                warn "$service container not found — may have crashed"
                log "Check: docker compose logs $service"
                return 1
            fi
        else
            local state health
            state=$(docker inspect --format='{{.State.Status}}' "$cid" 2>/dev/null || echo "unknown")
            health=$(docker inspect --format='{{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}}' "$cid" 2>/dev/null || echo "")

            if [ "$health" = "healthy" ]; then
                ok "$service is healthy (${elapsed}s)"
                return 0
            elif [ "$state" = "exited" ] || [ "$state" = "dead" ]; then
                warn "$service has crashed (state=$state)"
                log "Check: docker compose logs $service"
                return 1
            elif [ "$health" = "none" ] && [ "$state" = "running" ]; then
                ok "$service is running (${elapsed}s) [no healthcheck]"
                return 0
            fi
            # state=running but health=starting/unhealthy → keep waiting
        fi

        sleep 5
        elapsed=$((elapsed + 5))
    done

    warn "$service did not become healthy within ${max}s — continuing anyway"
    return 1
}

# Wait for init container to exit
wait_container_exit() {
    local service=$1
    local max=${2:-120}
    local elapsed=0

    log "Waiting for $service to complete..."
    while [ $elapsed -lt $max ]; do
        local cid
        cid=$($COMPOSE ps -q "$service" 2>/dev/null | head -1)

        if [ -z "$cid" ]; then
            ok "$service completed (${elapsed}s)"
            return 0
        fi

        local state
        state=$(docker inspect --format='{{.State.Status}}' "$cid" 2>/dev/null || echo "exited")

        if [ "$state" = "exited" ]; then
            ok "$service completed (${elapsed}s)"
            return 0
        fi

        sleep 3
        elapsed=$((elapsed + 3))
    done

    warn "$service did not complete within ${max}s"
}

# ── Prerequisites ──
check_prerequisites() {
    header "Checking Prerequisites"

    command -v docker &>/dev/null || fail "Docker not found"
    ok "Docker $(docker --version | awk '{print $3}')"

    docker compose version &>/dev/null || fail "Docker Compose not found"
    ok "Docker Compose $(docker compose version --short)"

    local ram_kb ram_gb
    ram_kb=$(grep MemTotal /proc/meminfo 2>/dev/null | awk '{print $2}' || echo "0")
    ram_gb=$((ram_kb / 1024 / 1024))
    if [ "$ram_gb" -lt 8 ] && [ "$ram_gb" -gt 0 ]; then
        warn "RAM: ${ram_gb}GB (recommend ≥ 8GB)"
    else
        ok "RAM: ${ram_gb}GB"
    fi

    local disk_gb
    disk_gb=$(df -BG "$PROJECT_DIR" 2>/dev/null | awk 'NR==2 {print $4}' | tr -d 'G')
    if [ "${disk_gb:-0}" -lt 20 ]; then
        warn "Disk: ${disk_gb}GB (recommend ≥ 20GB)"
    else
        ok "Disk: ${disk_gb}GB available"
    fi

    [ -f "$PROJECT_DIR/infrastructure/docker/docker-compose.yml" ] || fail "docker-compose.yml not found"
    ok "Project: $PROJECT_DIR"
}


# ============================================================================
# PHASE 1: Foundation & Data Ingestion
# ============================================================================
phase1() {
    header "PHASE 1: Foundation & Data Ingestion"

    # ── 1.0 Check for stale containers ──
    local running
    running=$($COMPOSE ps -q 2>/dev/null | wc -l)
    if [ "$running" -gt 0 ]; then
        log "Found $running running containers. Stopping first..."
        $COMPOSE down 2>/dev/null || true
        sleep 2
    fi

    # ── 1.1 Start storage & broker ──
    log "Starting infrastructure..."
    $COMPOSE up -d zookeeper
    wait_healthy zookeeper 60

    $COMPOSE up -d kafka
    if ! wait_healthy kafka 90; then
        warn "Kafka failed — likely Cluster ID mismatch. Auto-fixing..."
        $COMPOSE rm -f -s kafka 2>/dev/null || true
        docker volume rm "$(basename "$PROJECT_DIR" | tr '[:upper:]' '[:lower:]' | tr ' ' '_')_kafka-data" 2>/dev/null || true
        # Also reset zookeeper to get matching cluster ID
        $COMPOSE rm -f -s zookeeper 2>/dev/null || true
        docker volume rm "$(basename "$PROJECT_DIR" | tr '[:upper:]' '[:lower:]' | tr ' ' '_')_zookeeper-data" 2>/dev/null || true
        log "Restarting Zookeeper + Kafka with fresh volumes..."
        $COMPOSE up -d zookeeper
        wait_healthy zookeeper 60
        $COMPOSE up -d kafka
        wait_healthy kafka 90 || fail "Kafka failed even after volume reset"
    fi

    $COMPOSE up -d mongo
    wait_healthy mongo 60

    $COMPOSE up -d postgres
    wait_healthy postgres 180

    $COMPOSE up -d minio
    wait_healthy minio 60

    $COMPOSE up -d clickhouse
    wait_healthy clickhouse 120

    # ── 1.2 Kafka topics ──
    log "Creating Kafka topics..."
    $COMPOSE up -d kafka-init
    wait_container_exit kafka-init 60

    log "Verifying Kafka topics..."
    local topic_output topic_count kafka_cid
    kafka_cid=$(get_cid kafka)
    topic_output=$(timeout 10 docker exec "$kafka_cid" \
        kafka-topics --bootstrap-server localhost:9092 --list 2>/dev/null || true)
    topic_count=$(echo "$topic_output" | grep -c "^news\." || true)
    # Sanitize to integer
    topic_count=$(echo "$topic_count" | tr -d '[:space:]')
    topic_count=${topic_count:-0}

    if [[ "$topic_count" =~ ^[0-9]+$ ]] && [ "$topic_count" -ge 10 ]; then
        ok "Kafka: $topic_count topics created"
    else
        warn "Kafka: $topic_count topics found (expected 10)"
    fi

    # ── 1.3 Verify schemas ──
    log "Verifying PostgreSQL schemas..."
    sleep 3

    local schema_count
    schema_count=$(dc_psql "SELECT COUNT(*) FROM information_schema.schemata WHERE schema_name IN ('raw','staging','warehouse','mart')")
    schema_count=${schema_count:-0}

    if [[ "$schema_count" =~ ^[0-9]+$ ]] && [ "$schema_count" -ge 4 ]; then
        ok "PostgreSQL: $schema_count schemas ready"
    else
        warn "Schemas: $schema_count/4 found. Creating manually..."
        dc_exec postgres psql -U "$PG_USER" -d "$PG_DB" -c \
            "CREATE SCHEMA IF NOT EXISTS raw; CREATE SCHEMA IF NOT EXISTS staging; CREATE SCHEMA IF NOT EXISTS warehouse; CREATE SCHEMA IF NOT EXISTS mart;" \
            || warn "Schema creation failed"

        # Run migration files if tables don't exist
        local table_count
        table_count=$(dc_psql "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema IN ('raw','staging','warehouse')")
        table_count=${table_count:-0}

        if [[ "$table_count" =~ ^[0-9]+$ ]] && [ "$table_count" -lt 5 ]; then
            log "Running migration files..."
            for f in 1_create_schema.sql 2_create_raw_table.sql 3_create_staging_schema.sql 4_dimension_tables.sql 5_fact_and_bridges.sql 6_mart_tables.sql; do
                if dc_exec postgres test -f "/docker-entrypoint-initdb.d/$f"; then
                    log "  Running $f..."
                    dc_exec postgres psql -U "$PG_USER" -d "$PG_DB" -f "/docker-entrypoint-initdb.d/$f" || warn "  $f failed"
                fi
            done
            ok "Migrations applied"
        else
            ok "Tables already exist ($table_count tables)"
        fi
    fi

    # ── 1.4 Airflow ──
    log "Starting Airflow database..."
    $COMPOSE up -d airflow-db
    wait_healthy airflow-db 60

    log "Initializing Airflow (migrations + admin user)..."
    $COMPOSE up -d airflow-init
    wait_container_exit airflow-init 180

    log "Starting Airflow webserver + scheduler (this takes 2-5 minutes)..."
    $COMPOSE up -d airflow-webserver airflow-scheduler
    wait_healthy airflow-webserver 300
    wait_healthy airflow-scheduler 120

    ok "Airflow UI: http://localhost:${AIRFLOW_PORT:-8080} (admin/admin)"

    # ── 1.5 MongoDB collection ──
    log "Verifying MongoDB..."
    dc_exec mongo mongosh --quiet --eval "db.getSiblingDB('newspulse').createCollection('articles_raw')" || true
    ok "MongoDB: newspulse.articles_raw ready"

    # ── 1.6 Test crawl ──
    if [ "$SKIP_CRAWL" = false ]; then
        log "Running test crawl (VnExpress, 10 articles)..."
        dc_exec airflow-scheduler \
            bash -c "cd /opt/airflow/crawlers && scrapy crawl vnexpress -a max_articles=10 -s LOG_LEVEL=WARNING" || {
            warn "Test crawl failed — crawlers may need debugging"
        }

        sleep 5
        local article_count
        article_count=$(dc_exec mongo mongosh --quiet --eval \
            "db.getSiblingDB('newspulse').articles_raw.countDocuments()" \
            | tr -d '[:space:]' || true)
        article_count=${article_count:-0}

        if [[ "$article_count" =~ ^[0-9]+$ ]] && [ "$article_count" -gt 0 ]; then
            ok "Test crawl: $article_count articles in MongoDB"
        else
            warn "No articles in MongoDB — check crawler logs"
        fi
    else
        warn "Crawl skipped (--skip-crawl)"
    fi

    ok "Phase 1 complete!"
}


# ============================================================================
# PHASE 2: Processing & Data Warehouse
# ============================================================================
phase2() {
    header "PHASE 2: Processing & Data Warehouse"

    # ── 2.1 Spark ──
    log "Starting Spark..."
    if has_service "spark-master"; then
        $COMPOSE up -d spark-master
        sleep 10
        if has_service "spark-worker"; then
            $COMPOSE up -d spark-worker
            sleep 10
        fi
        ok "Spark UI: http://localhost:8082"
        
        log "Submitting NLP Spark Streaming Job..."
        dc_exec spark-master bash -c "nohup /opt/spark/bin/spark-submit \\
            --master spark://spark-master:7077 \\
            --conf spark.jars.ivy=/tmp/.ivy2 \\
            --packages org.apache.spark:spark-sql-kafka-0-10_2.12:3.5.0,com.clickhouse:clickhouse-jdbc:0.4.6 \\
            /opt/spark-apps/spark/streaming/streaming_job.py > /tmp/spark_streaming.log 2>&1 &"
        ok "Spark Streaming Job submitted to background"
    elif [ -f "$PROJECT_DIR/infrastructure/docker/docker-compose.spark.yml" ]; then
        docker compose -f "$PROJECT_DIR/infrastructure/docker/docker-compose.spark.yml" up -d 2>/dev/null || {
            warn "Spark failed to start — check docker-compose.spark.yml"
        }
        sleep 15
        # Verify Spark master is running
        if docker ps --filter "name=newspulse-spark-master" --filter "status=running" -q | grep -q .; then
            ok "Spark UI: http://localhost:8082"
        else
            warn "Spark master not running — check: docker compose -f infrastructure/docker/docker-compose.spark.yml logs spark-master"
        fi
    else
        warn "Spark not found in docker-compose — skipping"
    fi

    # ── 2.2 ELT pipeline ──
    log "Running ELT pipeline..."

    local raw_count
    raw_count=$(dc_psql "SELECT COUNT(*) FROM raw.articles" || true)
    raw_count=${raw_count:-0}
    log "Raw layer: $raw_count articles"

    dc_exec airflow-scheduler \
        bash -c "cd /opt/airflow && python -c 'from warehouse.etl.run_pipeline import run_full_pipeline; run_full_pipeline()'" || {
        warn "ELT pipeline failed — may need debugging"
    }

    # ── 2.3 Verify ──
    log "Verifying warehouse..."
    local fact_count dim_src dim_cat
    fact_count=$(dc_psql "SELECT COUNT(*) FROM warehouse.fact_article" || true)
    dim_src=$(dc_psql "SELECT COUNT(*) FROM warehouse.dim_source" || true)
    dim_cat=$(dc_psql "SELECT COUNT(*) FROM warehouse.dim_category" || true)

    ok "Warehouse: fact=${fact_count:-0}, sources=${dim_src:-0}, categories=${dim_cat:-0}"
    ok "Phase 2 complete!"
}


# ============================================================================
# PHASE 3: Serving & Dashboard
# ============================================================================
phase3() {
    header "PHASE 3: Serving & Dashboard"

    # ── FastAPI ──
    if has_service "api"; then
        log "Starting FastAPI..."
        $COMPOSE up -d api
        sleep 15
        # Use python to check health (curl may not be available in the container)
        local api_code
        api_code=$(dc_exec api python -c "
import urllib.request
try:
    r = urllib.request.urlopen('http://localhost:8000/health', timeout=5)
    print(r.status)
except Exception:
    print('000')
" || echo "000")
        api_code=$(echo "$api_code" | tr -d '[:space:]')
        if [ "$api_code" = "200" ]; then
            ok "FastAPI: http://localhost:8000/docs"
        else
            warn "FastAPI: HTTP $api_code — check: docker compose logs api"
        fi
    else
        warn "API service not in infrastructure/docker/docker-compose.yml"
    fi


    # ── Refresh marts ──
    log "Refreshing mart tables..."
    dc_exec postgres psql -U "$PG_USER" -d "$PG_DB" -c \
        "SELECT mart.refresh_materialized_views();" || {
        warn "Materialized views not available yet"
    }

    ok "Phase 3 complete!"
}


# ============================================================================
# PHASE 4: Monitoring & Verification
# ============================================================================
phase4() {
    header "PHASE 4: Monitoring & Verification"

    # ── Health checks ──
    log "Running health checks..."
    dc_exec airflow-scheduler \
        bash -c "cd /opt/airflow && python infrastructure/monitoring/health_monitor.py" || {
        warn "Health monitor not available. Manual check:"
        echo ""
        $COMPOSE ps
    }

    # ── Data quality ──
    log "Running data quality checks..."
    dc_exec airflow-scheduler \
        bash -c "cd /opt/airflow && python data_platform/data_quality/run_validations.py" || {
        warn "DQ runner not available. Row counts:"
        dc_exec postgres psql -U "$PG_USER" -d "$PG_DB" -c "
            SELECT 'raw.articles' AS tbl, COUNT(*) FROM raw.articles
            UNION ALL SELECT 'staging.articles', COUNT(*) FROM staging.articles
            UNION ALL SELECT 'warehouse.fact_article', COUNT(*) FROM warehouse.fact_article
            UNION ALL SELECT 'warehouse.dim_source', COUNT(*) FROM warehouse.dim_source
            UNION ALL SELECT 'warehouse.dim_category', COUNT(*) FROM warehouse.dim_category
            ORDER BY 1;
        " || warn "Could not query PostgreSQL"
    }

    # ── Performance indexes ──
    if [ -f "$PROJECT_DIR/data_platform/warehouse/migrations/7_performance_indexes.sql" ]; then
        log "Applying performance indexes..."
        dc_exec postgres psql -U "$PG_USER" -d "$PG_DB" \
            -f "/docker-entrypoint-initdb.d/7_performance_indexes.sql" || {
            warn "Performance indexes failed"
        }
        ok "Performance indexes applied"
    fi

    ok "Phase 4 complete!"
}


# ============================================================================
# SUMMARY
# ============================================================================
print_summary() {
    header "🚀 NewsPulse is Ready!"

    echo -e "  ${GREEN}Services:${NC}"
    echo -e "    Airflow UI      → ${CYAN}http://localhost:${AIRFLOW_PORT:-8080}${NC}  (admin/admin)"
    echo -e "    FastAPI Docs    → ${CYAN}http://localhost:${API_PORT:-8000}/docs${NC}"
    echo -e "    Spark UI        → ${CYAN}http://localhost:8082${NC}"
    echo -e "    Metabase        → ${CYAN}http://localhost:${METABASE_PORT:-3000}${NC}"
    echo -e "    Superset        → ${CYAN}http://localhost:8088${NC}"

    echo ""
    echo -e "  ${GREEN}Commands:${NC}"
    echo -e "    docker compose ps                    # Status"
    echo -e "    docker compose logs -f <service>     # Logs"
    echo -e "    docker compose down                  # Stop (keep data)"
    echo -e "    docker compose down -v               # Stop + delete data"
    echo ""
}


# ============================================================================
# MAIN
# ============================================================================
main() {
    cd "$PROJECT_DIR"

    header "NewsPulse — Master Startup"
    log "Project: $PROJECT_DIR"
    log "Phase: ${PHASE:-all}"

    if [ "$RESET" = true ]; then
        warn "Resetting all data..."
        $COMPOSE down -v 2>/dev/null || true
        ok "All volumes removed"
    fi

    check_prerequisites

    case "$PHASE" in
        1) phase1 ;;
        2) phase2 ;;
        3) phase3 ;;
        4) phase4 ;;
        "")
            phase1
            phase2
            phase3
            phase4
            ;;
        *) fail "Invalid phase: $PHASE (use 1-4)" ;;
    esac

    print_summary
}

main "$@"