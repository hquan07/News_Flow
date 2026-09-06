from fastapi import APIRouter, Query
from typing import Optional

from api.models.schemas import TimeRangeEnum
from api.services.analytics import get_trending_keywords

router = APIRouter(prefix="/trending", tags=["Trending Topics"])


@router.get("/keywords")
def trending_keywords(
        time_range: TimeRangeEnum = Query(default=TimeRangeEnum.week),
        limit: int = Query(default=20, ge=1, le=50),
        source: Optional[str] = Query(None),
        category: Optional[str] = Query(None),
):
    return get_trending_keywords(
        time_range=time_range.value, limit=limit,
        source=source, category=category,
    )
