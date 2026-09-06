from fastapi import APIRouter, Query
from typing import Optional

from api.models.schemas import TimeRangeEnum
from api.services.analytics import (
    get_sentiment_distribution,
    get_sentiment_timeline,
    get_sentiment_by_source,
)

router = APIRouter(prefix="/sentiment", tags=["Sentiment Intelligence"])

@router.get("/distribution")
def sentiment_distribution(
        time_range: TimeRangeEnum = Query(default=TimeRangeEnum.week),
        source: Optional[str] = Query(None),
        category: Optional[str] = Query(None),
):
    """
    Returns overall sentiment distribution (Positive/Negative/Neutral counts).
    """
    data = get_sentiment_distribution(time_range=time_range.value, source=source, category=category)
    return {"data": data}


@router.get("/timeline")
def sentiment_timeline(
        time_range: TimeRangeEnum = Query(default=TimeRangeEnum.week),
):
    """
    Returns sentiment counts by hour.
    """
    data = get_sentiment_timeline(time_range=time_range.value)
    return {"data": data}


@router.get("/sources")
def sentiment_by_source(
        time_range: TimeRangeEnum = Query(default=TimeRangeEnum.week),
):
    """
    Returns sentiment breakdown grouped by source.
    """
    data = get_sentiment_by_source(time_range=time_range.value)
    return {"data": data}
