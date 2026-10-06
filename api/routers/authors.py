from typing import Literal, Optional

from fastapi import APIRouter, Query

from api.services.author_analytics import get_author_analytics


router = APIRouter(prefix="/authors", tags=["Authors"])


@router.get("")
def author_analytics(
    time_range: Literal["today", "7d", "30d", "all"] = Query("all"),
    source: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=100),
):
    return get_author_analytics(
        time_range=time_range,
        source=source,
        limit=limit,
    )
