from fastapi import APIRouter, Query

from api.services import advanced_analytics


router = APIRouter(prefix="/insights", tags=["Advanced Insights"])


@router.get("/propagation")
def propagation(keyword: str = Query(min_length=2, max_length=120), days: int = Query(default=7, ge=1, le=30)):
    return advanced_analytics.propagation(keyword, days)


@router.get("/source-divergence/{event_id}")
def source_divergence(event_id: str):
    return advanced_analytics.source_divergence(event_id)


@router.get("/nlp-explanation/{article_id}")
def nlp_explanation(article_id: str):
    return advanced_analytics.nlp_explanation(article_id)


@router.get("/forecast")
def forecast(metric: str = Query(default="articles", pattern="^(articles|sentiment)$"), horizon: int = Query(default=6, ge=1, le=48)):
    return advanced_analytics.forecast(metric, horizon)
