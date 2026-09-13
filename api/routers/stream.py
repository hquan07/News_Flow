import asyncio
import json
from datetime import datetime
from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from api.services.analytics import get_social_crisis_alerts, get_viral_post_alerts
from api.routers.alerts import current_thresholds

router = APIRouter(prefix="/stream", tags=["Stream"])


async def event_generator():
    """Mock SSE generator that also checks for real alerts."""
    while True:
        await asyncio.sleep(5)
        
        # Poll alerts
        try:
            crisis = get_social_crisis_alerts(current_thresholds.crisis_negative_pct, current_thresholds.crisis_min_posts)
            viral = get_viral_post_alerts(current_thresholds.viral_interactions)
            
            if crisis or viral:
                data = json.dumps({
                    "timestamp": datetime.now().isoformat(),
                    "type": "social_alerts",
                    "crisis": crisis,
                    "viral": viral,
                })
                yield f"event: alert\ndata: {data}\n\n"
        except Exception as e:
            print(f"SSE Alert Error: {e}")
            
        data = json.dumps({
            "timestamp": datetime.now().isoformat(),
            "type": "heartbeat",
        })
        yield f"event: update\ndata: {data}\n\n"


@router.get("/")
async def sse_stream():
    return StreamingResponse(event_generator(), media_type="text/event-stream")
