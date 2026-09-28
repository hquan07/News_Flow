from fastapi import APIRouter, Query, Body, HTTPException
from api.services.analytics import get_alerts, get_social_crisis_alerts, get_viral_post_alerts, get_viral_post_detail
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime
import logging

logger = logging.getLogger("newspulse.alerts")


class SimpleSpikeAlert(BaseModel):
    hour_slot: datetime
    article_count: int
    avg_count: int

class SocialCrisisAlert(BaseModel):
    source: str
    total_posts: int
    negative_posts: int
    negative_pct: float

class AlertDataQuality(BaseModel):
    title_available: bool = True
    content_available: bool = True
    url_available: bool = False
    synthetic: bool = False

class ViralPostAlertSummary(BaseModel):
    post_id: str
    source: str
    title: str
    interactions: int
    sentiment_label: Optional[str] = None
    publish_time: Optional[str] = None
    data_quality: AlertDataQuality = AlertDataQuality()

class ViralPostDetail(BaseModel):
    post_id: str
    source: str
    title: str
    content: str
    excerpt: str
    url: str
    author: str
    like_count: int
    reply_count: int
    interactions: int
    upvote_ratio: float
    sentiment_score: float
    sentiment_label: str
    top_comments: List[str] = []
    publish_time: Optional[str] = None
    crawled_at: Optional[str] = None
    data_quality: AlertDataQuality = AlertDataQuality()

class SocialAlertsResponse(BaseModel):
    crisis_alerts: List[SocialCrisisAlert]
    viral_alerts: List[ViralPostAlertSummary]

class AlertThresholds(BaseModel):
    crisis_negative_pct: float = 30.0
    crisis_min_posts: int = 10
    viral_interactions: int = 50

# In-memory config for MVP
current_thresholds = AlertThresholds()

router = APIRouter(prefix="/alerts", tags=["Alerts & Anomalies"])

@router.get("/config", response_model=AlertThresholds)
def get_config():
    return current_thresholds

@router.post("/config", response_model=AlertThresholds)
def update_config(config: AlertThresholds = Body(...)):
    global current_thresholds
    current_thresholds = config
    return current_thresholds

@router.get("", response_model=dict)
def alerts(
        threshold: float = Query(default=2.0, description="Standard deviations above mean to trigger alert"),
        limit: int = Query(default=10, description="Max number of alerts to return"),
):
    results = get_alerts(threshold=threshold, limit=limit)
    return {"spikes": results}

@router.get("/social", response_model=SocialAlertsResponse)
def social_alerts():
    crisis = get_social_crisis_alerts(
        negative_pct_threshold=current_thresholds.crisis_negative_pct,
        min_posts=current_thresholds.crisis_min_posts
    )
    viral = get_viral_post_alerts(
        interaction_threshold=current_thresholds.viral_interactions
    )
    return SocialAlertsResponse(
        crisis_alerts=crisis,
        viral_alerts=viral
    )

@router.get("/social/posts/{post_id}", response_model=ViralPostDetail)
def get_social_post_detail(post_id: str):
    """Fetch full detail for a single viral/social post."""
    try:
        detail = get_viral_post_detail(post_id)
    except Exception as exc:
        logger.error("Failed to fetch detail for post_id=%s: %s", post_id, exc)
        raise HTTPException(status_code=503, detail="Data warehouse unavailable")
    if detail is None:
        raise HTTPException(status_code=404, detail="Post not found")
    return detail
