from fastapi import APIRouter, Query
from typing import Optional
from collections import defaultdict
from api.services.analytics import _query, _resolve_time_range, _append_filters

router = APIRouter(prefix="/social", tags=["Social"])

@router.get("/overview")
def social_overview(
        time_range: str = Query("7d"),
        source: Optional[str] = Query(None),
):
    where = _resolve_time_range(time_range, "publish_time")
    params = {}
    if source:
        where += " AND source = {source:String}"
        params["source"] = source
        
    daily_data = _query(
        f"SELECT source, "
        f"count() as post_count, "
        f"sum(like_count) as total_likes, "
        f"sum(reply_count) as total_replies, "
        f"avg(sentiment_score) as avg_sentiment "
        f"FROM newspulse.social_sentiment_metrics WHERE {where} "
        f"GROUP BY source",
        params,
    )
    
    total_posts = sum(row.get("post_count", 0) for row in daily_data)
    total_likes = sum(row.get("total_likes", 0) for row in daily_data)
    total_replies = sum(row.get("total_replies", 0) for row in daily_data)
    
    # Sentiment distribution
    sentiment_data = _query(
        f"SELECT sentiment_label, count() as count "
        f"FROM newspulse.social_sentiment_metrics WHERE {where} "
        f"GROUP BY sentiment_label",
        params,
    )
    sentiment_dist = [{"sentiment": row["sentiment_label"], "count": row["count"]} for row in sentiment_data]
    
    # Timeline
    timeline_data = _query(
        f"SELECT toStartOfHour(publish_time) as time, "
        f"countIf(sentiment_label = 'positive') as Positive, "
        f"countIf(sentiment_label = 'negative') as Negative, "
        f"countIf(sentiment_label = 'neutral') as Neutral "
        f"FROM newspulse.social_sentiment_metrics WHERE {where} "
        f"GROUP BY time ORDER BY time",
        params
    )
    sentiment_timeline = [
        {
            "time": row["time"].isoformat() if hasattr(row["time"], "isoformat") else str(row["time"]),
            "Positive": row["Positive"],
            "Negative": row["Negative"],
            "Neutral": row["Neutral"]
        } for row in timeline_data
    ]

    # Source distribution
    source_dist = [{"source": row["source"], "count": row["post_count"]} for row in daily_data]

    # Top debates (highest replies)
    top_debates_data = _query(
        f"SELECT post_id, source, title, content, reply_count, like_count, sentiment_score, publish_time "
        f"FROM newspulse.social_sentiment_metrics WHERE {where} "
        f"ORDER BY reply_count DESC LIMIT 20",
        params
    )
    
    return {
        "kpi_cards": [
            {"label": "Total Social Posts", "value": total_posts},
            {"label": "Total Likes", "value": total_likes},
            {"label": "Total Replies", "value": total_replies},
            {"label": "Active Platforms", "value": len(daily_data)}
        ],
        "sentiment_distribution": sentiment_dist,
        "sentiment_timeline": sentiment_timeline,
        "source_distribution": source_dist,
        "top_debates": top_debates_data
    }
