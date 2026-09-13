from fastapi import APIRouter, Query, Body
from api.services.analytics import get_alerts, get_social_crisis_alerts, get_viral_post_alerts
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime

class SimpleSpikeAlert(BaseModel):
    hour_slot: datetime
    article_count: int
    avg_count: int

class SocialCrisisAlert(BaseModel):
    source: str
    total_posts: int
    negative_posts: int
    negative_pct: float

class ViralPostAlert(BaseModel):
    post_id: str
    source: str
    title: str
    interactions: int
    sentiment_label: Optional[str] = None

class SocialAlertsResponse(BaseModel):
    crisis_alerts: List[SocialCrisisAlert]
    viral_alerts: List[ViralPostAlert]

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