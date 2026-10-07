from datetime import datetime, timezone
from fastapi import APIRouter, Query
from typing import Optional
from api.services.analytics import (
    _query,
    _resolve_time_range,
    _append_filters,
    get_recent_social_posts,
)

router = APIRouter(prefix="/social", tags=["Social"])


def _social_filters(time_range: str, source: Optional[str]):
    """Build the shared, parameterized filter used by social analytics views."""
    where = _resolve_time_range(time_range, "publish_time")
    return _append_filters(where, {}, source=source)


def _deduplicate_posts(posts):
    """Keep the highest-ranked row for each source/post identity."""
    seen = set()
    unique_posts = []
    for post in posts:
        identity = (str(post.get("source", "")), str(post.get("post_id", "")))
        if identity in seen:
            continue
        seen.add(identity)
        unique_posts.append(post)
    return unique_posts

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


@router.get("/content-performance")
def social_content_performance(
        time_range: str = Query("7d"),
        source: Optional[str] = Query(None),
        limit: int = Query(10, ge=1, le=50),
):
    """Summarize content output and rank posts by observed interactions."""
    where, params = _social_filters(time_range, source)

    summary_rows = _query(
        f"SELECT count() AS total_posts, "
        f"sum(like_count + reply_count) AS total_interactions, "
        f"if(count() = 0, 0, round(avg(like_count + reply_count), 1)) AS avg_interactions_per_post, "
        f"countIf((like_count + reply_count) >= 50) AS high_performing_posts "
        f"FROM newspulse.social_sentiment_metrics WHERE {where}",
        params,
    )
    summary = summary_rows[0] if summary_rows else {
        "total_posts": 0,
        "total_interactions": 0,
        "avg_interactions_per_post": 0,
        "high_performing_posts": 0,
    }

    platform_performance = _query(
        f"SELECT source, count() AS post_count, sum(like_count) AS total_likes, "
        f"sum(reply_count) AS total_replies, "
        f"sum(like_count + reply_count) AS total_interactions, "
        f"round(avg(like_count + reply_count), 1) AS avg_interactions_per_post "
        f"FROM newspulse.social_sentiment_metrics WHERE {where} "
        f"GROUP BY source ORDER BY total_interactions DESC",
        params,
    )

    top_posts = _query(
        f"SELECT post_id, source, author, title, content, like_count, reply_count, "
        f"(like_count + reply_count) AS interactions, sentiment_label, publish_time "
        f"FROM newspulse.social_sentiment_metrics WHERE {where} "
        f"ORDER BY interactions DESC, publish_time DESC LIMIT {{limit:UInt32}}",
        {**params, "limit": limit},
    )
    top_posts = _deduplicate_posts(top_posts)

    return {
        "summary": summary,
        "platform_performance": platform_performance,
        "top_posts": top_posts,
        "time_range": time_range,
    }


@router.get("/audience")
def social_audience(
        time_range: str = Query("7d"),
        source: Optional[str] = Query(None),
):
    """Describe participating authors and when the social audience is active."""
    where, params = _social_filters(time_range, source)

    summary_rows = _query(
        f"SELECT count() AS total_posts, "
        f"uniqExactIf(author, notEmpty(trim(author))) AS unique_contributors, "
        f"uniqExact(source) AS active_platforms "
        f"FROM newspulse.social_sentiment_metrics WHERE {where}",
        params,
    )
    raw_summary = summary_rows[0] if summary_rows else {}
    total_posts = int(raw_summary.get("total_posts", 0) or 0)
    unique_contributors = int(raw_summary.get("unique_contributors", 0) or 0)

    activity_by_hour = _query(
        f"SELECT toHour(publish_time) AS hour, count() AS post_count, "
        f"uniqExactIf(author, notEmpty(trim(author))) AS active_contributors, "
        f"sum(like_count + reply_count) AS interactions "
        f"FROM newspulse.social_sentiment_metrics WHERE {where} "
        f"GROUP BY hour ORDER BY hour",
        params,
    )
    peak = max(activity_by_hour, key=lambda row: row.get("post_count", 0), default=None)

    contributor_segments = _query(
        f"SELECT multiIf(post_count = 1, 'One-time', post_count <= 5, 'Occasional', 'Core') AS segment, "
        f"count() AS contributors "
        f"FROM (SELECT author, count() AS post_count "
        f"FROM newspulse.social_sentiment_metrics WHERE {where} "
        f"AND notEmpty(trim(author)) GROUP BY author) "
        f"GROUP BY segment ORDER BY contributors DESC",
        params,
    )

    platform_audience = _query(
        f"SELECT source, count() AS post_count, "
        f"uniqExactIf(author, notEmpty(trim(author))) AS contributors, "
        f"sum(like_count + reply_count) AS interactions "
        f"FROM newspulse.social_sentiment_metrics WHERE {where} "
        f"GROUP BY source ORDER BY contributors DESC, post_count DESC",
        params,
    )

    return {
        "summary": {
            "total_posts": total_posts,
            "unique_contributors": unique_contributors,
            "active_platforms": int(raw_summary.get("active_platforms", 0) or 0),
            "avg_posts_per_contributor": round(total_posts / unique_contributors, 1)
            if unique_contributors else 0,
            "peak_hour": int(peak["hour"]) if peak is not None else None,
        },
        "activity_by_hour": activity_by_hour,
        "contributor_segments": contributor_segments,
        "platform_audience": platform_audience,
        "time_range": time_range,
        "methodology": "Audience metrics represent authors and channels that published or replied, not passive viewers or reach.",
    }


@router.get("/topics")
def social_topics(
        time_range: str = Query("7d"),
        source: Optional[str] = Query(None),
        limit: int = Query(20, ge=1, le=50),
):
    """Extract popular hashtags and rank recurring conversation titles."""
    where, params = _social_filters(time_range, source)

    hashtags = _query(
        f"SELECT lowerUTF8(hashtag) AS hashtag, count() AS mentions, "
        f"sum(interactions) AS interactions "
        f"FROM (SELECT arrayJoin(extractAll(concat(title, ' ', content), "
        f"'(#[[:alnum:]_]+)')) AS hashtag, (like_count + reply_count) AS interactions "
        f"FROM newspulse.social_sentiment_metrics WHERE {where}) "
        f"WHERE notEmpty(hashtag) GROUP BY hashtag "
        f"ORDER BY mentions DESC, interactions DESC LIMIT {{limit:UInt32}}",
        {**params, "limit": limit},
    )

    top_topics = _query(
        f"SELECT if(empty(trim(title)), substringUTF8(content, 1, 120), title) AS topic, "
        f"any(source) AS source, count() AS post_count, "
        f"sum(like_count + reply_count) AS interactions, "
        f"round(avg(sentiment_score), 3) AS sentiment_score "
        f"FROM newspulse.social_sentiment_metrics WHERE {where} "
        f"AND (notEmpty(trim(title)) OR notEmpty(trim(content))) "
        f"GROUP BY topic ORDER BY interactions DESC, post_count DESC "
        f"LIMIT {{limit:UInt32}}",
        {**params, "limit": limit},
    )

    return {
        "summary": {
            "unique_hashtags": len(hashtags),
            "hashtag_mentions": sum(int(row.get("mentions", 0) or 0) for row in hashtags),
            "tracked_topics": len(top_topics),
            "topic_interactions": sum(int(row.get("interactions", 0) or 0) for row in top_topics),
        },
        "hashtags": hashtags,
        "top_topics": top_topics,
        "time_range": time_range,
    }


@router.get("/alert-signals")
def social_alert_signals(
        source: Optional[str] = Query(None),
        negative_pct_threshold: float = Query(30.0, ge=0, le=100),
        min_posts: int = Query(10, ge=1, le=10000),
        interaction_threshold: int = Query(50, ge=1),
):
    """Return recent sentiment-risk and viral-content signals for social monitoring."""
    where, params = _social_filters("today", source)

    source_rows = _query(
        f"SELECT source, count() AS total_posts, "
        f"countIf(sentiment_label = 'negative') AS negative_posts, "
        f"round(if(count() = 0, 0, countIf(sentiment_label = 'negative') / count() * 100), 1) AS negative_pct, "
        f"sum(like_count + reply_count) AS interactions "
        f"FROM newspulse.social_sentiment_metrics WHERE {where} "
        f"GROUP BY source ORDER BY negative_pct DESC, total_posts DESC",
        params,
    )
    source_risks = [
        {
            **row,
            "active": (
                int(row.get("total_posts", 0) or 0) >= min_posts
                and float(row.get("negative_pct", 0) or 0) >= negative_pct_threshold
            ),
        }
        for row in source_rows
    ]

    viral_posts = _query(
        f"SELECT post_id, source, author, title, content, like_count, reply_count, "
        f"(like_count + reply_count) AS interactions, sentiment_label, publish_time "
        f"FROM newspulse.social_sentiment_metrics WHERE {where} "
        f"AND (like_count + reply_count) >= {{interaction_threshold:Int32}} "
        f"ORDER BY interactions DESC, publish_time DESC LIMIT 20",
        {**params, "interaction_threshold": interaction_threshold},
    )
    viral_posts = _deduplicate_posts(viral_posts)
    active_source_risks = [row for row in source_risks if row["active"]]

    return {
        "summary": {
            "active_alerts": len(active_source_risks) + len(viral_posts),
            "crisis_sources": len(active_source_risks),
            "viral_posts": len(viral_posts),
            "negative_posts": sum(int(row.get("negative_posts", 0) or 0) for row in source_rows),
        },
        "source_risks": source_risks,
        "viral_posts": viral_posts,
        "thresholds": {
            "negative_pct": negative_pct_threshold,
            "min_posts": min_posts,
            "interactions": interaction_threshold,
        },
        "window": "Last 24 hours",
        "generated_at": datetime.now(timezone.utc).isoformat(),
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
