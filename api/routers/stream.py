import asyncio
import json
import logging
import time
from datetime import datetime, timezone
from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

from api.services.analytics import get_social_crisis_alerts, get_viral_post_alerts
from api.config import get_settings
from api.services.alert_metrics import alert_metrics
from api.services.alert_config import get_alert_thresholds

router = APIRouter(prefix="/stream", tags=["Stream"])
logger = logging.getLogger("newspulse.stream")


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
        await asyncio.sleep(5)
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
                yield f"event: alert\ndata: {data}\n\n"
                alert_metrics.observe("sse_snapshot", "success", 0)
        except Exception:
            alert_metrics.observe("sse_snapshot", "error", 0)
            logger.exception("Failed to refresh SSE alerts")
            
        data = json.dumps({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "type": "heartbeat",
        })
        yield f"event: update\ndata: {data}\n\n"


@router.get("")
@router.get("/", include_in_schema=False)
async def sse_stream(request: Request):
    return StreamingResponse(
        event_generator(request),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
