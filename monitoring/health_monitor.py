"""
NewsPulse Phase 4A: System Health Monitor
==========================================
Script kiểm tra toàn bộ hệ thống, có thể chạy standalone hoặc từ Airflow.

Usage:
    python monitoring/health_monitor.py              # Check all services
    python monitoring/health_monitor.py --json        # JSON output
    python monitoring/health_monitor.py --service pg  # Check specific service

Exit codes:
    0 = All healthy
    1 = One or more services unhealthy
"""

import argparse
import json
import socket
import sys
import time
from datetime import datetime, timezone
from typing import Any

from loguru import logger

# ---------------------------------------------------------------------------
# Configuration — auto-detect Docker (inside container) vs host environment
# Inside Airflow container: PG_HOST=postgres, MONGO_URI=mongodb://mongo:27017
# On host machine: override via env or .env file
# ---------------------------------------------------------------------------
import os


def _is_docker():
    """Detect if running inside a Docker container."""
    return os.path.exists("/.dockerenv") or os.getenv("AIRFLOW_HOME") is not None


# Use Docker service names when inside container, localhost when on host
_default_host = "localhost"
if _is_docker():
    _default_host = None  # Will use service-specific defaults below

CONFIG = {
    "mongodb": {
        "host": os.getenv("MONGO_HOST", "mongo" if _is_docker() else "localhost"),
        "port": int(os.getenv("MONGO_PORT", "27017")),
        "db": os.getenv("MONGO_DB", "newspulse"),
    },
    "postgresql": {
        "host": os.getenv("PG_HOST", "postgres" if _is_docker() else "localhost"),
        "port": int(os.getenv("PG_PORT", "5432")),
        "user": os.getenv("PG_USER", "newspulse"),
        "password": os.getenv("PG_PASSWORD", "newspulse"),
        "dbname": os.getenv("PG_DB", "newspulse"),
    },
    "kafka": {
        "bootstrap_servers": os.getenv(
            "KAFKA_BOOTSTRAP_SERVERS",
            os.getenv("KAFKA_BOOTSTRAP", "kafka:9092" if _is_docker() else "localhost:9092"),
        ),
    },
    "spark": {
        "master_ui": os.getenv("SPARK_MASTER_UI", "http://spark-master:8082" if _is_docker() else "http://localhost:8082"),
    },
    "airflow": {
        "webserver_url": os.getenv("AIRFLOW_URL", "http://airflow-webserver:8080" if _is_docker() else "http://localhost:8080"),
    },
    "api": {
        "url": os.getenv("API_URL", "http://newspulse-api:8000" if _is_docker() else "http://localhost:8000"),
    },
}


# ---------------------------------------------------------------------------
# Health check functions
# ---------------------------------------------------------------------------

def check_tcp(host: str, port: int, timeout: float = 5.0) -> bool:
    """Basic TCP connectivity check."""
    try:
        sock = socket.create_connection((host, port), timeout=timeout)
        sock.close()
        return True
    except (socket.timeout, ConnectionRefusedError, OSError):
        return False


def check_mongodb() -> dict[str, Any]:
    """Check MongoDB connectivity and data presence."""
    cfg = CONFIG["mongodb"]
    start = time.monotonic()

    if not check_tcp(cfg["host"], cfg["port"]):
        return {"status": "unhealthy", "error": f"TCP connection failed on port {cfg['port']}"}

    try:
        from pymongo import MongoClient

        client = MongoClient(
            cfg["host"], cfg["port"],
            serverSelectionTimeoutMS=5000,
        )
        db = client[cfg["db"]]
        db.command("ping")

        # Data freshness check
        articles = db["articles_raw"]
        total = articles.estimated_document_count()

        result = {
            "status": "healthy",
            "latency_ms": round((time.monotonic() - start) * 1000, 1),
            "total_articles": total,
        }

        # Check latest article timestamp
        latest = articles.find_one(sort=[("crawl_time", -1)])
        if latest and "crawl_time" in latest:
            result["latest_crawl"] = str(latest["crawl_time"])

        client.close()
        return result

    except ImportError:
        return {"status": "unknown", "error": "pymongo not installed"}
    except Exception as e:
        return {"status": "unhealthy", "error": str(e)}


def check_postgresql() -> dict[str, Any]:
    """Check PostgreSQL connectivity, schema layers, and data presence."""
    cfg = CONFIG["postgresql"]
    start = time.monotonic()

    if not check_tcp(cfg["host"], cfg["port"]):
        return {"status": "unhealthy", "error": f"TCP connection failed on port {cfg['port']}"}

    try:
        import psycopg2

        conn = psycopg2.connect(
            host=cfg["host"],
            port=cfg["port"],
            user=cfg["user"],
            password=cfg["password"],
            dbname=cfg["dbname"],
            connect_timeout=5,
        )
        cur = conn.cursor()

        # Check schemas exist
        cur.execute("""
            SELECT schema_name
            FROM information_schema.schemata
            WHERE schema_name IN ('raw', 'staging', 'warehouse', 'mart', 'public')
            ORDER BY schema_name
        """)
        schemas = [row[0] for row in cur.fetchall()]

        # Check fact table row count
        fact_count = 0
        try:
            cur.execute("SELECT COUNT(*) FROM warehouse.fact_article")
            fact_count = cur.fetchone()[0]
        except Exception:
            conn.rollback()

        # Check mart tables
        mart_tables = []
        try:
            cur.execute("""
                SELECT table_name FROM information_schema.tables
                WHERE table_schema = 'mart' ORDER BY table_name
            """)
            mart_tables = [row[0] for row in cur.fetchall()]
        except Exception:
            conn.rollback()

        cur.close()
        conn.close()

        return {
            "status": "healthy",
            "latency_ms": round((time.monotonic() - start) * 1000, 1),
            "schemas": schemas,
            "fact_article_count": fact_count,
            "mart_tables": mart_tables,
        }

    except ImportError:
        return {"status": "unknown", "error": "psycopg2 not installed"}
    except Exception as e:
        return {"status": "unhealthy", "error": str(e)}


def check_kafka() -> dict[str, Any]:
    """Check Kafka broker connectivity and topic info."""
    cfg = CONFIG["kafka"]
    start = time.monotonic()

    # Parse host:port from bootstrap_servers
    bs = cfg["bootstrap_servers"].split(",")[0]
    host, port = bs.rsplit(":", 1)
    if not check_tcp(host, int(port)):
        return {"status": "unhealthy", "error": f"TCP connection failed to {bs}"}

    try:
        from kafka import KafkaAdminClient
        from kafka.errors import KafkaError

        admin = KafkaAdminClient(
            bootstrap_servers=cfg["bootstrap_servers"],
            request_timeout_ms=5000,
        )
        topics = admin.list_topics()
        user_topics = sorted([t for t in topics if not t.startswith("__")])

        # Check consumer group lag (optional)
        consumer_groups = []
        try:
            consumer_groups = [g[0] for g in admin.list_consumer_groups()]
        except Exception:
            pass

        admin.close()

        return {
            "status": "healthy",
            "latency_ms": round((time.monotonic() - start) * 1000, 1),
            "topics": user_topics,
            "consumer_groups": consumer_groups,
        }

    except ImportError:
        return {"status": "unknown", "error": "kafka-python not installed"}
    except Exception as e:
        return {"status": "unhealthy", "error": str(e)}


def check_spark() -> dict[str, Any]:
    """Check Spark Master via REST API."""
    cfg = CONFIG["spark"]
    start = time.monotonic()

    try:
        import requests

        resp = requests.get(f"{cfg['master_ui']}/json/", timeout=5)
        resp.raise_for_status()
        data = resp.json()

        return {
            "status": "healthy",
            "latency_ms": round((time.monotonic() - start) * 1000, 1),
            "spark_status": data.get("status", "unknown"),
            "alive_workers": data.get("aliveworkers", 0),
            "cores_used": data.get("coresused", 0),
            "memory_used": data.get("memoryused", "0"),
            "active_apps": len(data.get("activeapps", [])),
        }

    except ImportError:
        return {"status": "unknown", "error": "requests not installed"}
    except Exception as e:
        return {"status": "unhealthy", "error": str(e)}


def check_airflow() -> dict[str, Any]:
    """Check Airflow webserver health endpoint."""
    cfg = CONFIG["airflow"]
    start = time.monotonic()

    try:
        import requests

        resp = requests.get(f"{cfg['webserver_url']}/health", timeout=5)
        resp.raise_for_status()
        data = resp.json()

        return {
            "status": "healthy",
            "latency_ms": round((time.monotonic() - start) * 1000, 1),
            "scheduler": data.get("scheduler", {}).get("status", "unknown"),
            "metadatabase": data.get("metadatabase", {}).get("status", "unknown"),
        }

    except ImportError:
        return {"status": "unknown", "error": "requests not installed"}
    except Exception as e:
        return {"status": "unhealthy", "error": str(e)}


def check_api() -> dict[str, Any]:
    """Check FastAPI health endpoint."""
    cfg = CONFIG["api"]
    start = time.monotonic()

    try:
        import requests

        resp = requests.get(f"{cfg['url']}/health", timeout=5)
        resp.raise_for_status()

        return {
            "status": "healthy",
            "latency_ms": round((time.monotonic() - start) * 1000, 1),
        }

    except ImportError:
        return {"status": "unknown", "error": "requests not installed"}
    except Exception as e:
        return {"status": "unhealthy", "error": str(e)}


# ---------------------------------------------------------------------------
# Service registry
# ---------------------------------------------------------------------------

SERVICE_CHECKS = {
    "mongodb":    ("MongoDB",    check_mongodb),
    "pg":         ("PostgreSQL", check_postgresql),
    "kafka":      ("Kafka",      check_kafka),
    "spark":      ("Spark",      check_spark),
    "airflow":    ("Airflow",    check_airflow),
    "api":        ("FastAPI",    check_api),
}


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

def run_checks(services: list[str] | None = None) -> dict:
    """Run health checks cho danh sách services (hoặc tất cả)."""
    if services is None:
        services = list(SERVICE_CHECKS.keys())

    results = {}
    for svc_key in services:
        if svc_key not in SERVICE_CHECKS:
            logger.warning(f"Unknown service: {svc_key}")
            continue

        name, check_fn = SERVICE_CHECKS[svc_key]
        logger.info(f"Checking {name}...")
        try:
            results[svc_key] = check_fn()
            results[svc_key]["name"] = name
        except Exception as e:
            results[svc_key] = {"name": name, "status": "error", "error": str(e)}

    all_healthy = all(
        r.get("status") == "healthy"
        for r in results.values()
    )

    return {
        "overall": "healthy" if all_healthy else "degraded",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "services": results,
    }


def print_report(report: dict) -> None:
    """In báo cáo dạng bảng ra console."""
    status_icon = {"healthy": "✅", "unhealthy": "❌", "degraded": "⚠️", "unknown": "❓"}

    print("\n" + "=" * 60)
    print(f"  NewsPulse Health Report — {report['timestamp']}")
    print(f"  Overall: {status_icon.get(report['overall'], '?')} {report['overall'].upper()}")
    print("=" * 60)

    for key, svc in report["services"].items():
        icon = status_icon.get(svc["status"], "?")
        name = svc.get("name", key)
        latency = svc.get("latency_ms", "—")
        print(f"\n  {icon} {name} ({svc['status']})")

        if svc.get("latency_ms"):
            print(f"     Latency: {latency}ms")
        if svc.get("error"):
            print(f"     Error: {svc['error']}")

        # Service-specific info
        for k, v in svc.items():
            if k in ("status", "name", "latency_ms", "error"):
                continue
            print(f"     {k}: {v}")

    print("\n" + "=" * 60 + "\n")


# ---------------------------------------------------------------------------
# Airflow-callable function
# ---------------------------------------------------------------------------

def airflow_health_check(**kwargs) -> None:
    """
    Callable từ Airflow PythonOperator.
    Raise exception nếu có service unhealthy → DAG task fail → trigger alert.
    """
    report = run_checks()

    # Push report to XCom
    ti = kwargs.get("ti")
    if ti:
        ti.xcom_push(key="health_report", value=report)

    if report["overall"] != "healthy":
        unhealthy = [
            f"{v['name']}: {v.get('error', 'unknown')}"
            for v in report["services"].values()
            if v["status"] != "healthy"
        ]
        raise RuntimeError(
            f"Health check failed! Unhealthy services:\n"
            + "\n".join(f"  - {s}" for s in unhealthy)
        )

    logger.info("All services healthy ✅")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="NewsPulse Health Monitor")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    parser.add_argument(
        "--service", "-s",
        choices=list(SERVICE_CHECKS.keys()),
        nargs="+",
        help="Check specific service(s) only",
    )
    args = parser.parse_args()

    report = run_checks(services=args.service)

    if args.json:
        print(json.dumps(report, indent=2, default=str))
    else:
        print_report(report)

    sys.exit(0 if report["overall"] == "healthy" else 1)


if __name__ == "__main__":
    main()