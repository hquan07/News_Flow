import asyncio

from fastapi import APIRouter, Query, Depends, HTTPException
from api.services.analytics import (
    get_alerts,
    get_social_crisis_alerts,
    get_social_crisis_detail,
    get_viral_post_alerts,
    get_viral_post_detail,
    get_volume_spike_detail,
    get_interaction_trend,
)
from api.security import get_admin_user
from api.services.alert_state import get_alert_states, update_alert_state
from api.services.alert_metrics import alert_metrics
from api.services.alert_config import get_alert_thresholds, update_alert_thresholds
from pydantic import BaseModel, Field, model_validator
from typing import List, Literal, Optional
from datetime import datetime, timezone
import logging
from time import monotonic

logger = logging.getLogger("newspulse.alerts")


class SimpleSpikeAlert(BaseModel):
    alert_id: str = ""
    hour_slot: datetime
    article_count: int
    avg_count: int
    std_count: float = 0
    z_score: float = 0
    threshold: float = 2
    alert_reason: str = ""

class SocialCrisisAlert(BaseModel):
    alert_id: str = ""
    source: str
    total_posts: int
    negative_posts: int
    negative_pct: float
    negative_pct_threshold: float = 30
    min_posts_threshold: int = 10
    alert_reason: str = ""

class AlertDataQuality(BaseModel):
    title_available: bool = True
    content_available: bool = True
    url_available: bool = False
    synthetic: bool = False

class ViralPostAlertSummary(BaseModel):
    alert_id: str = ""
    post_id: str
    source: str
    title: str
    interactions: int
    sentiment_label: Optional[str] = None
    publish_time: Optional[str] = None
    threshold: int = 50
    alert_reason: str = ""
    data_quality: AlertDataQuality = Field(default_factory=AlertDataQuality)

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
    top_comments: List[str] = Field(default_factory=list)
    publish_time: Optional[str] = None
    crawled_at: Optional[str] = None
    data_quality: AlertDataQuality = Field(default_factory=AlertDataQuality)

class SentimentBucket(BaseModel):
    label: str
    count: int

class SocialCrisisDetail(SocialCrisisAlert):
    sentiment_distribution: List[SentimentBucket] = Field(default_factory=list)
    top_negative_posts: List[ViralPostAlertSummary] = Field(default_factory=list)

class VolumeArticle(BaseModel):
    article_id: str
    title: str
    url: str
    source: str
    category: str
    publish_time: datetime

class VolumeSpikeDetail(BaseModel):
    hour_slot: datetime
    window_end: datetime
    article_count: int
    avg_count: float
    std_count: float
    z_score: float
    threshold: float
    is_active: bool
    alert_reason: str
    articles: List[VolumeArticle] = Field(default_factory=list)

class SocialAlertsResponse(BaseModel):
    crisis_alerts: List[SocialCrisisAlert]
    viral_alerts: List[ViralPostAlertSummary]
    generated_at: datetime

class AlertThresholds(BaseModel):
    crisis_negative_pct: float = 30.0
    crisis_min_posts: int = 10
    viral_interactions: int = 50

class AlertStateQuery(BaseModel):
    alert_ids: List[str] = Field(default_factory=list, max_length=100)

class AlertStatePatch(BaseModel):
    pinned: Optional[bool] = None
    acknowledged: Optional[bool] = None

    @model_validator(mode="after")
    def require_update(self):
        if self.pinned is None and self.acknowledged is None:
            raise ValueError("At least one alert state field is required")
        return self

class AlertState(BaseModel):
    alert_id: str
    user_id: str
    pinned: bool = False
    acknowledged: bool = False
    created_at: datetime
    updated_at: datetime

class InteractionTrendPoint(BaseModel):
    bucket: datetime
    interactions: int
    post_count: int

class InteractionTrendResponse(BaseModel):
    source: Optional[str] = None
    granularity: Literal["15m", "1h"]
    data: List[InteractionTrendPoint] = Field(default_factory=list)

router = APIRouter(prefix="/alerts", tags=["Alerts & Anomalies"])

@router.get("/config", response_model=AlertThresholds)
async def get_config():
    return await get_alert_thresholds()

@router.post("/config", response_model=AlertThresholds)
async def update_config(
    config: AlertThresholds,
    user: dict = Depends(get_admin_user),
):
    return await update_alert_thresholds(config.model_dump(), user["sub"])

@router.get("", response_model=dict)
def alerts(
        threshold: float = Query(default=2.0, description="Standard deviations above mean to trigger alert"),
        limit: int = Query(default=10, description="Max number of alerts to return"),
):
    results = get_alerts(threshold=threshold, limit=limit)
    return {"spikes": results}

@router.get("/social", response_model=SocialAlertsResponse)
async def social_alerts():
    started = monotonic()
    outcome = "success"
    try:
        thresholds = await get_alert_thresholds()
        crisis, viral = await asyncio.gather(
            asyncio.to_thread(
                get_social_crisis_alerts,
                thresholds["crisis_negative_pct"],
                thresholds["crisis_min_posts"],
            ),
            asyncio.to_thread(
                get_viral_post_alerts,
                thresholds["viral_interactions"],
            ),
        )
        return SocialAlertsResponse(
            crisis_alerts=crisis,
            viral_alerts=viral,
            generated_at=datetime.now(timezone.utc),
        )
    except Exception:
        outcome = "error"
        raise
    finally:
        alert_metrics.observe("social_snapshot", outcome, monotonic() - started)


@router.get("/social/trends", response_model=InteractionTrendResponse)
def social_interaction_trend(
    source: Optional[str] = Query(default=None),
    granularity: Literal["15m", "1h"] = Query(default="15m"),
):
    started = monotonic()
    outcome = "success"
    try:
        return get_interaction_trend(source=source, granularity=granularity)
    except Exception:
        outcome = "error"
        raise
    finally:
        alert_metrics.observe("interaction_trend", outcome, monotonic() - started)


@router.get("/metrics", response_model=dict)
async def get_alert_metrics(_user: dict = Depends(get_admin_user)):
    """Return telemetry aggregated from active API workers."""
    return await alert_metrics.shared_snapshot()


@router.post("/state/query", response_model=List[AlertState])
async def query_alert_states(
    query: AlertStateQuery,
    user: dict = Depends(get_admin_user),
):
    started = monotonic()
    outcome = "success"
    try:
        return await get_alert_states(user["sub"], query.alert_ids)
    except Exception:
        outcome = "error"
        raise
    finally:
        alert_metrics.observe("state_query", outcome, monotonic() - started)


@router.patch("/state/{alert_id}", response_model=AlertState)
async def patch_alert_state(
    alert_id: str,
    patch: AlertStatePatch,
    user: dict = Depends(get_admin_user),
):
    started = monotonic()
    outcome = "success"
    try:
        return await update_alert_state(
            user["sub"],
            alert_id,
            pinned=patch.pinned,
            acknowledged=patch.acknowledged,
        )
    except Exception:
        outcome = "error"
        raise
    finally:
        alert_metrics.observe("state_update", outcome, monotonic() - started)

@router.get("/social/posts/{post_id}", response_model=ViralPostDetail)
def get_social_post_detail(post_id: str):
    """Fetch full detail for a single viral/social post."""
    started = monotonic()
    outcome = "success"
    try:
        detail = get_viral_post_detail(post_id)
    except Exception as exc:
        outcome = "error"
        logger.error("Failed to fetch detail for post_id=%s: %s", post_id, exc)
        alert_metrics.observe("viral_detail", outcome, monotonic() - started)
        raise HTTPException(status_code=503, detail="Data warehouse unavailable")
    if detail is None:
        outcome = "not_found"
        alert_metrics.observe("viral_detail", outcome, monotonic() - started)
        raise HTTPException(status_code=404, detail="Post not found")
    alert_metrics.observe("viral_detail", outcome, monotonic() - started)
    return detail


@router.get("/social/crisis/{source}", response_model=SocialCrisisDetail)
async def get_crisis_detail(source: str):
    started = monotonic()
    outcome = "success"
    try:
        thresholds = await get_alert_thresholds()
        detail = await asyncio.to_thread(
            get_social_crisis_detail,
            source,
            thresholds["crisis_negative_pct"],
            thresholds["crisis_min_posts"],
        )
    except Exception as exc:
        outcome = "error"
        logger.error("Failed to fetch crisis detail for source=%s: %s", source, exc)
        alert_metrics.observe("crisis_detail", outcome, monotonic() - started)
        raise HTTPException(status_code=503, detail="Data warehouse unavailable")
    if detail is None:
        outcome = "not_found"
        alert_metrics.observe("crisis_detail", outcome, monotonic() - started)
        raise HTTPException(status_code=404, detail="Active crisis alert not found")
    alert_metrics.observe("crisis_detail", outcome, monotonic() - started)
    return detail


@router.get("/volume/{hour_slot}", response_model=VolumeSpikeDetail)
def get_spike_detail(hour_slot: datetime, threshold: float = Query(default=0.5, ge=0)):
    started = monotonic()
    outcome = "success"
    try:
        detail = get_volume_spike_detail(hour_slot, threshold=threshold)
    except Exception as exc:
        outcome = "error"
        logger.error("Failed to fetch spike detail for hour_slot=%s: %s", hour_slot, exc)
        alert_metrics.observe("volume_detail", outcome, monotonic() - started)
        raise HTTPException(status_code=503, detail="Data warehouse unavailable")
    if detail is None:
        outcome = "not_found"
        alert_metrics.observe("volume_detail", outcome, monotonic() - started)
        raise HTTPException(status_code=404, detail="Volume spike not found")
    alert_metrics.observe("volume_detail", outcome, monotonic() - started)
    return detail
