import asyncio
import time

from api.config import get_ch_client, get_settings
from api.database import get_mongo_db


async def _check_clickhouse() -> dict:
    started = time.monotonic()

    def ping() -> None:
        client = get_ch_client()
        try:
            client.command("SELECT 1")
        finally:
            client.close()

    await asyncio.to_thread(ping)
    return {
        "status": "healthy",
        "latency_ms": round((time.monotonic() - started) * 1000, 1),
    }


async def _check_mongodb() -> dict:
    started = time.monotonic()
    await get_mongo_db().command("ping")
    return {
        "status": "healthy",
        "latency_ms": round((time.monotonic() - started) * 1000, 1),
    }


async def dependency_health() -> dict:
    timeout = get_settings().HEALTHCHECK_TIMEOUT_SECONDS
    names = ("clickhouse", "mongodb")
    checks = (_check_clickhouse(), _check_mongodb())
    results = await asyncio.gather(
        *(asyncio.wait_for(check, timeout=timeout) for check in checks),
        return_exceptions=True,
    )

    services = {}
    for name, result in zip(names, results):
        if isinstance(result, Exception):
            services[name] = {
                "status": "unhealthy",
                "error": type(result).__name__,
            }
        else:
            services[name] = result

    ready = all(service["status"] == "healthy" for service in services.values())
    return {"status": "healthy" if ready else "degraded", "services": services}
