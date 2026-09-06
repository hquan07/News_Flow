from fastapi import APIRouter, Query
from typing import Optional
from collections import defaultdict

from api.models.schemas import TimeRangeEnum, OverviewResponse, KPICard
from api.services.analytics import get_overview, get_hourly_distribution, get_sentiment_distribution

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
    source_latencies = defaultdict(lambda: {"total_latency": 0.0, "count": 0})

    for row in daily_data:
        count = row.get("article_count", 0)
        total_articles += count
        src = row.get("source")
        sources.add(src)
        category_counts[row.get("category")] += count

        latency = row.get("avg_crawl_latency")
        if latency and count:
            total_latency_sum += float(latency) * count
            if src:
                source_latencies[src]["total_latency"] += float(latency) * count
                source_latencies[src]["count"] += count

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
        h = int(row["hour"])
        hour_counts[h] += row["total_count"]
    articles_by_hour = [{"hour": f"{h:02d}", "count": hour_counts.get(h, 0)} for h in range(24)]

    source_speed = [
        {
            "source": src,
            "avg_latency_min": round(vals["total_latency"] / vals["count"], 1) if vals["count"] > 0 else 0,
            "article_count": vals["count"],
        }
        for src, vals in source_latencies.items()
    ]

    sentiment_data = get_sentiment_distribution(time_range=time_range.value, source=source, category=category)
    sentiment_dist = [{"sentiment": row["sentiment_label"], "count": row["count"]} for row in sentiment_data]

    return OverviewResponse(
        kpi_cards=kpi_cards,
        articles_by_hour=articles_by_hour,
        category_distribution=cat_dist,
        source_speed=source_speed,
        sentiment_distribution=sentiment_dist,
    )