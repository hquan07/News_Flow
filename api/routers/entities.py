from fastapi import APIRouter, Query
from typing import Optional

from api.models.schemas import TimeRangeEnum, EntityTypeEnum
from api.services.analytics import get_entity_stats

router = APIRouter(prefix="/entities", tags=["Entity Intelligence"])


@router.get("")
def top_entities(
        entity_type: Optional[EntityTypeEnum] = Query(
            default=None, description="Filter by entity type: PER, LOC, ORG"
        ),
        time_range: TimeRangeEnum = Query(default=TimeRangeEnum.week),
        limit: int = Query(default=20, ge=1, le=50),
        source: Optional[str] = Query(None),
        category: Optional[str] = Query(None),
):
    type_val = entity_type.value if entity_type else None
    return get_entity_stats(
        time_range=time_range.value, entity_type=type_val,
        limit=limit, source=source, category=category,
    )
