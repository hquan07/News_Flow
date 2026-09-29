from fastapi import APIRouter, Query
from typing import Optional
from collections import defaultdict
from api.services.analytics import (
    _query,
    _resolve_time_range,
    _append_filters,
    get_recent_social_posts,
)

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
        f"sum(reply_count) as total_replies "
        f"FROM newspulse.social_sentiment_metrics WHERE {where} "
        f"GROUP BY source",
        params,
    )
    
    total_posts = sum(row.get("post_count", 0) for row in daily_data)
    total_likes = sum(row.get("total_likes", 0) for row in daily_data)
    total_replies = sum(row.get("total_replies", 0) for row in daily_data)
    
    # Timeline for Engagement
    timeline_data = _query(
        f"SELECT toStartOfHour(publish_time) as time, "
        f"sum(like_count) as Likes, "
        f"sum(reply_count) as Replies "
        f"FROM newspulse.social_sentiment_metrics WHERE {where} "
        f"GROUP BY time ORDER BY time",
        params
    )
    engagement_timeline = [
        {
            "time": row["time"].isoformat() if hasattr(row["time"], "isoformat") else str(row["time"]),
            "Likes": row["Likes"],
            "Replies": row["Replies"]
        } for row in timeline_data
    ]

    # Source distribution
    source_dist = [{"source": row["source"], "count": row["post_count"]} for row in daily_data]
    likes_dist = [{"source": row["source"], "count": row["total_likes"]} for row in daily_data]
    replies_dist = [{"source": row["source"], "count": row["total_replies"]} for row in daily_data]

    return {
        "kpi_cards": [
            {"label": "Total Social Posts", "value": total_posts},
            {"label": "Total Likes", "value": total_likes},
            {"label": "Total Replies", "value": total_replies},
            {"label": "Active Platforms", "value": len(daily_data)}
        ],
        "engagement_timeline": engagement_timeline,
        "source_distribution": source_dist,
        "likes_distribution": likes_dist,
        "replies_distribution": replies_dist
    }

@router.get("/sentiment")
def social_sentiment(
        time_range: str = Query("7d"),
        source: Optional[str] = Query(None),
):
    where = _resolve_time_range(time_range, "publish_time")
    params = {}
    if source:
        where += " AND source = {source:String}"
        params["source"] = source
        
    # Sentiment distribution
    sentiment_data = _query(
        f"SELECT sentiment_label, count() as count "
        f"FROM newspulse.social_sentiment_metrics WHERE {where} "
        f"GROUP BY sentiment_label",
        params,
    )
    sentiment_dist = [{"sentiment_label": row["sentiment_label"].capitalize(), "count": row["count"]} for row in sentiment_data]
    
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
    
    # Sentiment by Source
    sentiment_by_source_data = _query(
        f"SELECT source, "
        f"countIf(sentiment_label = 'positive') as Positive, "
        f"countIf(sentiment_label = 'negative') as Negative, "
        f"countIf(sentiment_label = 'neutral') as Neutral "
        f"FROM newspulse.social_sentiment_metrics WHERE {where} "
        f"GROUP BY source",
        params
    )
    sentiment_by_source = [
        {
            "source": row["source"],
            "Positive": row["Positive"],
            "Negative": row["Negative"],
            "Neutral": row["Neutral"]
        } for row in sentiment_by_source_data
    ]
    
    return {
        "sentiment_distribution": sentiment_dist,
        "sentiment_timeline": sentiment_timeline,
        "sentiment_by_source": sentiment_by_source
    }

@router.get("/debates")
def social_debates(
        time_range: str = Query("7d"),
        source: Optional[str] = Query(None),
):
    where = _resolve_time_range(time_range, "publish_time")
    params = {}
    if source:
        where += " AND source = {source:String}"
        params["source"] = source
        
    # Top debates (highest replies)
    top_debates_data = _query(
        f"SELECT post_id, source, title, content, reply_count, like_count, sentiment_score, publish_time "
        f"FROM newspulse.social_sentiment_metrics WHERE {where} "
        f"ORDER BY reply_count DESC LIMIT 20",
        params
    )
    
    return {
        "top_debates": top_debates_data
    }


@router.get("/influencers")
def social_influencers(
        time_range: str = Query("7d"),
        source: Optional[str] = Query(None),
        limit: int = Query(20, ge=1, le=100),
):
    """Rank social authors/channels by total likes and replies."""
    where = _resolve_time_range(time_range, "publish_time")
    params = {"limit": limit}
    if source:
        where += " AND source = {source:String}"
        params["source"] = source

    rows = _query(
        f"SELECT "
        f"if(empty(trim(author)), concat(source, ' channel'), author) AS author, "
        f"source, count() AS post_count, "
        f"sum(like_count) AS total_likes, "
        f"sum(reply_count) AS total_replies, "
        f"sum(like_count + reply_count) AS total_interactions, "
        f"round(avg(sentiment_score), 3) AS avg_sentiment "
        f"FROM newspulse.social_sentiment_metrics WHERE {where} "
        f"GROUP BY author, source "
        f"ORDER BY total_interactions DESC, post_count DESC "
        f"LIMIT {{limit:UInt32}}",
        params,
    )

    return {
        "influencers": rows,
        "total": len(rows),
        "time_range": time_range,
    }


@router.get("/feed")
def social_feed(limit: int = Query(50, ge=1, le=100)):
    """Return a recent snapshot used to hydrate the realtime social feed."""
    posts = get_recent_social_posts(limit)
    return {"posts": posts, "total": len(posts)}
