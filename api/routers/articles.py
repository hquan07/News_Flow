from fastapi import APIRouter, HTTPException, Query
from typing import Optional
from datetime import date, datetime

from api.services.crud import get_articles, get_article_detail

router = APIRouter(prefix="/articles", tags=["Articles"])


@router.get("")
def list_articles(
        page: int = Query(default=1, ge=1),
        page_size: int = Query(default=20, ge=1, le=100),
        q: Optional[str] = Query(default=None, description="Search in title"),
        source: Optional[str] = Query(default=None),
        category: Optional[str] = Query(default=None),
        date_from: Optional[date] = Query(default=None),
        date_to: Optional[date] = Query(default=None),
        published_from: Optional[datetime] = Query(default=None),
        published_to: Optional[datetime] = Query(default=None),
        entity: Optional[str] = Query(default=None, description="Filter by entity"),
        keyword: Optional[str] = Query(default=None, description="Filter by keyword"),
        sentiment: Optional[str] = Query(default=None, pattern="^(positive|neutral|negative)$"),
):
    return get_articles(
        page=page, page_size=page_size, q=q, source=source,
        category=category, date_from=date_from, date_to=date_to,
        published_from=published_from, published_to=published_to,
        entity=entity, keyword=keyword, sentiment=sentiment,
    )


@router.get("/{article_id}")
def get_article(article_id: str):
    article = get_article_detail(article_id)
    if not article:
        raise HTTPException(status_code=404, detail="Article not found")
    return article
