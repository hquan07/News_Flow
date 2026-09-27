from fastapi import APIRouter
from datetime import datetime, timezone
from api.services.analytics import _query_one
from api.services.health import dependency_health

router = APIRouter(prefix="/public", tags=["Public"])

@router.get("/summary")
async def get_public_summary():
    try:
        # Check health first
        health_status = await dependency_health()
        if health_status["status"] != "healthy":
            return {
                "status": "unavailable",
                "articles_processed": 0,
                "active_sources": 0,
                "alerts_last_24h": 0,
                "last_updated_at": datetime.now(timezone.utc).isoformat()
            }

        # articles_processed
        articles_count_res = _query_one("SELECT count() AS count FROM newspulse.raw_articles")
        articles_processed = articles_count_res.get("count", 0) if articles_count_res else 0

        # active_sources
        sources_res = _query_one("SELECT uniq(source) AS count FROM newspulse.raw_articles")
        active_sources = sources_res.get("count", 0) if sources_res else 0
        
        # alerts_last_24h
        alerts_res = _query_one("SELECT count() AS count FROM newspulse.raw_articles WHERE publish_time >= now() - INTERVAL 24 HOUR")
        alerts_last_24h = 0 # Placeholder for actual alerts count
        
        return {
            "status": "healthy",
            "articles_processed": articles_processed,
            "active_sources": active_sources,
            "alerts_last_24h": alerts_last_24h,
            "last_updated_at": datetime.now(timezone.utc).isoformat()
        }
    except Exception as e:
        return {
            "status": "unavailable",
            "articles_processed": 0,
            "active_sources": 0,
            "alerts_last_24h": 0,
            "last_updated_at": datetime.now(timezone.utc).isoformat()
        }
