from fastapi import APIRouter, Query

from api.services.analytics import get_alerts

from pydantic import BaseModel
from typing import List
from datetime import datetime

class SimpleSpikeAlert(BaseModel):
    hour_slot: datetime
    article_count: int
    avg_count: int

class SimpleAlertsResponse(BaseModel):
    spikes: List[SimpleSpikeAlert]

router = APIRouter(prefix="/alerts", tags=["Alerts & Anomalies"])


@router.get("", response_model=SimpleAlertsResponse)
def alerts(
        threshold: float = Query(default=2.0, description="Standard deviations above mean to trigger alert"),
        limit: int = Query(default=10, description="Max number of alerts to return"),
):
    results = get_alerts(threshold=threshold, limit=limit)
    return SimpleAlertsResponse(spikes=results)