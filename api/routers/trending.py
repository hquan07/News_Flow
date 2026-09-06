from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional

from api.models.schemas import TimeRangeEnum
from api.services.analytics import (
    get_trending_keywords,
    get_keyword_timeline,
    get_co_occurrences,
)

router = APIRouter(prefix="/trending", tags=["Trending Topics"])


@router.get("/keywords")
def trending_keywords(
        time_range: TimeRangeEnum = Query(default=TimeRangeEnum.week),
        limit: int = Query(default=20, ge=1, le=50),
        source: Optional[str] = Query(None),
        category: Optional[str] = Query(None),
):
    return get_trending_keywords(time_range=time_range.value, limit=limit, source=source, category=category)


@router.get("/keywords/{keyword}/timeline")
def keyword_timeline(
        keyword: str,
        time_range: TimeRangeEnum = Query(default=TimeRangeEnum.month),
):
    return get_keyword_timeline(keyword=keyword, days=30)


@router.get("/co-occurrences")
def co_occurrences(
        time_range: TimeRangeEnum = Query(default=TimeRangeEnum.week),
        limit: int = Query(default=20, ge=1, le=50),
):
    return get_co_occurrences(limit=limit)
