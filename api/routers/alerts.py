from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from api.services.analytics import get_alerts

router = APIRouter(prefix="/alerts", tags=["Alerts & Anomalies"])


@router.get("")
def alerts(
        threshold: float = Query(default=2.0, description="Standard deviations above mean to trigger alert"),
        limit: int = Query(default=10, description="Max number of alerts to return")
):
    return get_alerts(threshold=threshold, limit=limit)