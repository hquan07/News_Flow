import os
import time
from datetime import datetime, timezone

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from loguru import logger
from pydantic import BaseModel

router = APIRouter(tags=["health"])


# Config (read from environment)
_PG_HOST = os.getenv("PG_HOST", "localhost")
_PG_PORT = os.getenv("PG_PORT", "5432")
_PG_USER = os.getenv("PG_USER", "newspulse")
_PG_PASSWORD = os.getenv("PG_PASSWORD", "newspulse")
_PG_DB = os.getenv("PG_DB", "newspulse")
_MONGO_HOST = os.getenv("MONGO_HOST", "localhost")
_MONGO_PORT = os.getenv("MONGO_PORT", "27017")

MONGO_URI = f"mongodb://{_MONGO_HOST}:{_MONGO_PORT}"
MONGO_DB = os.getenv("MONGO_DB", "newspulse")
PG_DSN = f"postgresql://{_PG_USER}:{_PG_PASSWORD}@{_PG_HOST}:{_PG_PORT}/{_PG_DB}"
KAFKA_BOOTSTRAP = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
SPARK_MASTER_URL = os.getenv("SPARK_MASTER_UI", "http://localhost:8082")


# Individual service checks
async def check_postgresql() -> dict:
    import asyncpg

    start = time.monotonic()
    try:
        conn = await asyncpg.connect(PG_DSN, timeout=5)
        row = await conn.fetchrow("SELECT COUNT(*) AS cnt FROM information_schema.tables WHERE table_schema = 'public'")
        await conn.close()
        return {
            "status": "healthy",
            "latency_ms": round((time.monotonic() - start) * 1000, 1),
            "public_tables": row["cnt"],
        }
    except Exception as e:
        return {"status": "unhealthy", "error": str(e)}


async def check_mongodb() -> dict:
    from motor.motor_asyncio import AsyncIOMotorClient

    start = time.monotonic()
    try:
        client = AsyncIOMotorClient(MONGO_URI, serverSelectionTimeoutMS=5000)
        db = client[MONGO_DB]
        await db.command("ping")
        collections = await db.list_collection_names()
        doc_count = await db["articles_raw"].estimated_document_count()
        client.close()
        return {
            "status": "healthy",
            "latency_ms": round((time.monotonic() - start) * 1000, 1),
            "collections": len(collections),
            "articles_raw_count": doc_count,
        }
    except Exception as e:
        return {"status": "unhealthy", "error": str(e)}


async def check_kafka() -> dict:
    from kafka import KafkaAdminClient
    from kafka.errors import KafkaError

    start = time.monotonic()
    try:
        admin = KafkaAdminClient(
            bootstrap_servers=KAFKA_BOOTSTRAP,
            request_timeout_ms=5000,
        )
        topics = admin.list_topics()
        admin.close()
        # Lọc bỏ internal topics
        user_topics = [t for t in topics if not t.startswith("__")]
        return {
            "status": "healthy",
            "latency_ms": round((time.monotonic() - start) * 1000, 1),
            "topics": user_topics,
            "topic_count": len(user_topics),
        }
    except Exception as e:
        return {"status": "unhealthy", "error": str(e)}


async def check_spark() -> dict:
    import httpx

    start = time.monotonic()
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.get(f"{SPARK_MASTER_URL}/json/")
            data = resp.json()
        return {
            "status": "healthy",
            "latency_ms": round((time.monotonic() - start) * 1000, 1),
            "alive_workers": data.get("aliveworkers", 0),
            "active_apps": len(data.get("activeapps", [])),
        }
    except Exception as e:
        return {"status": "unhealthy", "error": str(e)}


# Endpoints
@router.get("/health")
async def health_simple():
    return {"status": "ok", "timestamp": datetime.now(timezone.utc).isoformat()}


@router.get("/health/detailed")
async def health_detailed():
    import asyncio

    checks = await asyncio.gather(
        check_postgresql(),
        check_mongodb(),
        check_kafka(),
        check_spark(),
        return_exceptions=True,
    )

    # Map results, handle exceptions from gather
    service_names = ["postgresql", "mongodb", "kafka", "spark"]
    results = {}
    for name, result in zip(service_names, checks):
        if isinstance(result, Exception):
            results[name] = {"status": "unhealthy", "error": str(result)}
        else:
            results[name] = result

    all_healthy = all(r.get("status") == "healthy" for r in results.values())

    response = {
        "status": "healthy" if all_healthy else "degraded",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "services": results,
    }

    status_code = 200 if all_healthy else 503

    if not all_healthy:
        unhealthy = [k for k, v in results.items() if v.get("status") != "healthy"]
        logger.warning(f"Health check degraded — unhealthy services: {unhealthy}")

    return JSONResponse(content=response, status_code=status_code)