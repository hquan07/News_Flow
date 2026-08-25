from fastapi import APIRouter, Query
from collections import defaultdict

from api.models.schemas import TimeRangeEnum, SourceComparisonResponse, SourceCategorySplit
from api.services.analytics import get_source_comparison, get_overview

router = APIRouter(prefix="/sources", tags=["Source Comparison"])

from typing import Optional

@router.get("/comparison", response_model=SourceComparisonResponse)
def source_comparison(
        time_range: TimeRangeEnum = Query(default=TimeRangeEnum.week),
        source: Optional[str] = Query(None),
        category: Optional[str] = Query(None),
):
    src_data = get_source_comparison(time_range=time_range.value, source=source, category=category)
    avg_word_count = []
    
    for row in src_data:
        avg_word_count.append({
            "source": row["source"],
            "word_count": float(row["avg_word_count"]) if row["avg_word_count"] else 0.0
        })
        
    daily_data = get_overview(time_range=time_range.value)
    
    cat_split_map = defaultdict(int)
    source_totals = defaultdict(int)
    
    for row in daily_data:
        src = row.get("source")
        cat = row.get("category")
        count = row.get("article_count", 0)
        cat_split_map[(src, cat)] += count
        source_totals[src] += count
        
    category_split = []
    for (src, cat), count in cat_split_map.items():
        total = source_totals[src]
        pct = (count / total * 100) if total > 0 else 0
        category_split.append(
            SourceCategorySplit(
                source=src,
                category=cat,
                count=count,
                percentage=pct
            )
        )
        
    return SourceComparisonResponse(
        category_split=category_split,
        avg_word_count=avg_word_count,
        overlap=[],
        reaction_times=[]
    )