from datetime import datetime, timezone

from fastapi import APIRouter, Depends

from api.database import get_mongo_db
from api.security import get_admin_user
from api.services.analytics import _query
from api.services.health import dependency_health

router = APIRouter(prefix="/admin", tags=["Admin Dashboard"])


@router.get("/metrics/latency")
def get_crawl_latency(user: dict = Depends(get_admin_user)):
    """Lấy độ trễ trung bình khi cào dữ liệu (từ bài báo xuất bản đến lúc cào)."""
    query = """
        SELECT source, avg(crawl_latency_minutes) as avg_latency
        FROM newspulse.raw_articles
        WHERE crawl_latency_minutes IS NOT NULL
        GROUP BY source
        ORDER BY avg_latency DESC
    """
    df = _query(query)
    if not df:
        return {
            "sources": [],
            "avg_latency": [],
            "overall_average": 0,
            "unit": "minutes",
            "sla_target": 5,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

    latencies = [round(float(row["avg_latency"]), 2) for row in df]

    return {
        "sources": [row["source"] for row in df],
        "avg_latency": latencies,
        "overall_average": round(sum(latencies) / len(latencies), 2),
        "unit": "minutes",
        "sla_target": 5,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/metrics/volume")
def get_article_volume(user: dict = Depends(get_admin_user)):
    """Lấy tổng số bài viết theo nguồn, bao gồm cả News và Social."""
    query_news = """
        SELECT source, count(*) as total_articles
        FROM newspulse.raw_articles
        GROUP BY source
        ORDER BY total_articles DESC
    """
    df_news = _query(query_news)

    query_social = """
        SELECT source, count(*) as total_articles
        FROM newspulse.social_sentiment_metrics
        GROUP BY source
        ORDER BY total_articles DESC
    """
    df_social = _query(query_social)

    return {
        "news": {
            "sources": [row["source"] for row in df_news] if df_news else [],
            "volumes": [int(row["total_articles"]) for row in df_news]
            if df_news
            else [],
            "total": sum(int(row["total_articles"]) for row in df_news)
            if df_news
            else 0,
        },
        "social": {
            "sources": [row["source"] for row in df_social] if df_social else [],
            "volumes": [int(row["total_articles"]) for row in df_social]
            if df_social
            else [],
            "total": sum(int(row["total_articles"]) for row in df_social)
            if df_social
            else 0,
        },
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/metrics/users")
async def get_user_metrics(user: dict = Depends(get_admin_user)):
    """Lấy tổng số user từ MongoDB."""
    db = get_mongo_db()
    total_users = await db.users.count_documents({})
    admin_users = await db.users.count_documents({"role": "admin"})

    return {
        "total_users": total_users,
        "standard_users": total_users - admin_users,
        "admin_users": admin_users,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/metrics/health")
async def get_system_health(user: dict = Depends(get_admin_user)):
    result = await dependency_health()
    return {**result, "generated_at": datetime.now(timezone.utc).isoformat()}
