from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional

from api.database import get_pg_session
from api.models.schemas import TimeRangeEnum, EntityTypeEnum
from api.services.analytics import (
    get_entity_stats,
    get_entity_timeline,
    get_entities_by_category,
    get_entity_network,
)

router = APIRouter(prefix="/entities", tags=["Entity Intelligence"])

@router.get("/network")
def entity_network(
        time_range: TimeRangeEnum = Query(default=TimeRangeEnum.week),
        limit: int = Query(default=50, ge=10, le=200),
):
    return get_entity_network(time_range=time_range.value, limit=limit)



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
    return get_entity_stats(time_range=time_range.value, entity_type=type_val, limit=limit, source=source, category=category)


@router.get("/{entity_name}/timeline")
def entity_timeline(
        entity_name: str,
        time_range: TimeRangeEnum = Query(default=TimeRangeEnum.month),
):
    return get_entity_timeline(entity=entity_name, days=30)


@router.get("/by-category")
def entities_by_category(
        time_range: TimeRangeEnum = Query(default=TimeRangeEnum.week),
):
    return get_entities_by_category()
