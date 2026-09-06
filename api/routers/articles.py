from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional
from datetime import date

from api.services.crud import get_articles, get_article_detail, delete_article

router = APIRouter(prefix="/articles", tags=["Articles"])


@router.get("")
async def list_articles(
        page: int = Query(default=1, ge=1),
        page_size: int = Query(default=20, ge=1, le=100),
        q: Optional[str] = Query(default=None, description="Search in title"),
        source: Optional[str] = Query(default=None),
        category: Optional[str] = Query(default=None),
        date_from: Optional[date] = Query(default=None),
        date_to: Optional[date] = Query(default=None),
        entity: Optional[str] = Query(default=None, description="Filter by entity"),
        keyword: Optional[str] = Query(default=None, description="Filter by keyword"),
):
    result = get_articles(
        page=page,
        page_size=page_size,
        q=q,
        source=source,
        category=category,
        date_from=date_from,
        date_to=date_to,
        entity=entity,
        keyword=keyword,
    )
    return result


@router.get("/{article_id}")
async def get_article(article_id: str):
    article = get_article_detail(article_id)
    if not article:
        raise HTTPException(status_code=404, detail="Article not found")
    return article


@router.delete("/{article_id}")
async def remove_article(article_id: str):
    deleted = delete_article(article_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Article not found")
    return {"message": "Article deleted", "article_id": article_id}