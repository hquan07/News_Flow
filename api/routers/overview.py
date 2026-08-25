from fastapi import APIRouter, Query
from typing import Optional
from collections import defaultdict

from api.models.schemas import TimeRangeEnum, OverviewResponse, KPICard
from api.services.analytics import get_overview, get_hourly_distribution

router = APIRouter(prefix="/overview", tags=["Overview"])

@router.get("", response_model=OverviewResponse)
def overview(
        time_range: TimeRangeEnum = Query(
            default=TimeRangeEnum.today,
            description="Time range: today, 7d, 30d, all",
        ),
        source: Optional[str] = Query(None, description="Filter by source"),
        category: Optional[str] = Query(None, description="Filter by category"),
):
    daily_data = get_overview(time_range=time_range.value, source=source, category=category)
    
    total_articles = 0
    total_latency_sum = 0.0
    sources = set()
    category_counts = defaultdict(int)
    
    for row in daily_data:
        count = row.get("article_count", 0)
        total_articles += count
        sources.add(row.get("source"))
        category_counts[row.get("category")] += count
        if row.get("avg_crawl_latency"):
            total_latency_sum += float(row.get("avg_crawl_latency")) * count
        
    top_cat = max(category_counts.items(), key=lambda x: x[1])[0] if category_counts else "N/A"
    avg_latency = round(total_latency_sum / total_articles, 1) if total_articles > 0 else 0.0
    
    kpi_cards = [
        KPICard(label="Total articles", value=total_articles),
        KPICard(label="Active sources", value=len(sources)),
        KPICard(label="Top category", value=top_cat),
        KPICard(label="Avg latency", value=f"{avg_latency} min"),
    ]
    
    cat_dist = [{"category": k, "count": v} for k, v in category_counts.items()]
    
    hourly_data = get_hourly_distribution(time_range=time_range.value, source=source, category=category)
    hour_counts = defaultdict(int)
    for row in hourly_data:
        # row["hour"] might be int or decimal, cast to int
        h = int(row["hour"])
        hour_counts[h] += row["total_count"]
        
    articles_by_hour = [{"hour": f"{h:02d}", "count": hour_counts.get(h, 0)} for h in range(24)]
    
    # Get sentiment distribution
    from api.services.analytics import get_sentiment_distribution
    sentiment_data = get_sentiment_distribution(time_range=time_range.value, source=source, category=category)
    sentiment_dist = [{"sentiment": row["sentiment_label"], "count": row["count"]} for row in sentiment_data]
    
    return OverviewResponse(
        kpi_cards=kpi_cards,
        articles_by_hour=articles_by_hour,
        category_distribution=cat_dist,
        source_speed=[],
        sentiment_distribution=sentiment_dist
    )