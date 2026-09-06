import asyncio
import json
from datetime import datetime
from fastapi import APIRouter
from fastapi.responses import StreamingResponse

router = APIRouter(prefix="/stream", tags=["Stream"])

async def event_generator():
    """
    In production, this would subscribe to a Redis PubSub channel
    or poll ClickHouse for the newest inserted records.
    For demonstration, we mock real-time events.
    """
    while True:
        await asyncio.sleep(3)
        data = json.dumps({
            "timestamp": datetime.now().isoformat(),
            "type": "new_article",
            "message": "New data processed and inserted into warehouse."
        })
        yield f"event: update\ndata: {data}\n\n"

@router.get("/")
async def sse_stream():
    return StreamingResponse(event_generator(), media_type="text/event-stream")
