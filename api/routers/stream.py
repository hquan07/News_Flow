import asyncio
import json
import logging
import time
import itertools
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse

from api.services.analytics import get_social_crisis_alerts, get_viral_post_alerts
from api.config import get_settings
from api.services.alert_metrics import alert_metrics
from api.services.alert_config import get_alert_thresholds

router = APIRouter(prefix="/stream", tags=["Stream"])
logger = logging.getLogger("newspulse.stream")
event_ids = itertools.count(int(time.time() * 1000))


class SSEConnectionLimiter:
    def __init__(self):
        self._lock = asyncio.Lock()
        self._active = 0

    async def acquire(self, limit: int) -> bool:
        async with self._lock:
            if self._active >= limit:
                return False
            self._active += 1
            return True

    async def release(self) -> None:
        async with self._lock:
            self._active = max(self._active - 1, 0)


sse_connections = SSEConnectionLimiter()


class AlertCache:
    def __init__(self):
        self._lock = asyncio.Lock()
        self._updated_at = 0.0
        self._value = {"crisis": [], "viral": []}

    async def get(self) -> dict:
        ttl = get_settings().SSE_ALERT_CACHE_SECONDS
        now = time.monotonic()
        if now - self._updated_at < ttl:
            return self._value

        async with self._lock:
            now = time.monotonic()
            if now - self._updated_at < ttl:
                return self._value

            try:
                thresholds = await get_alert_thresholds()
                crisis, viral = await asyncio.gather(
                    asyncio.to_thread(
                        get_social_crisis_alerts,
                        thresholds["crisis_negative_pct"],
                        thresholds["crisis_min_posts"],
                    ),
                    asyncio.to_thread(
                        get_viral_post_alerts,
                        thresholds["viral_interactions"],
                    ),
                )
            except Exception:
                # Back off all connected clients together when a dependency is down.
                self._updated_at = time.monotonic()
                raise
            self._value = {"crisis": crisis, "viral": viral}
            self._updated_at = time.monotonic()
            return self._value


alert_cache = AlertCache()


async def event_generator(request: Request):
    """Stream shared alert snapshots and per-connection heartbeats."""
    while True:
        await asyncio.sleep(get_settings().SSE_HEARTBEAT_SECONDS)
        if await request.is_disconnected():
            break

        try:
            alerts = await alert_cache.get()
            crisis = alerts["crisis"]
            viral = alerts["viral"]
            if crisis or viral:
                data = json.dumps({
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "type": "social_alerts",
                    "crisis": crisis,
                    "viral": viral,
                }, default=str)
                yield _format_sse("alert", data)
                alert_metrics.observe("sse_snapshot", "success", 0)
        except Exception:
            alert_metrics.observe("sse_snapshot", "error", 0)
            logger.exception("Failed to refresh SSE alerts")
            
        data = json.dumps({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "type": "heartbeat",
        })
        yield _format_sse("update", data)


def _format_sse(event: str, data: str) -> str:
    return (
        f"id: {next(event_ids)}\n"
        f"retry: {get_settings().SSE_RETRY_MILLISECONDS}\n"
        f"event: {event}\n"
        f"data: {data}\n\n"
    )


async def guarded_event_generator(request: Request):
    try:
        async for event in event_generator(request):
            yield event
    finally:
        await sse_connections.release()


@router.get("")
@router.get("/", include_in_schema=False)
async def sse_stream(request: Request):
    if not await sse_connections.acquire(
        max(get_settings().SSE_MAX_CONNECTIONS_PER_WORKER, 1)
    ):
        raise HTTPException(status_code=503, detail="SSE connection capacity reached")
    return StreamingResponse(
        guarded_event_generator(request),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
