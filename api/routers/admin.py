from datetime import datetime, timezone
from random import choice, randint, uniform
from uuid import uuid4

from fastapi import APIRouter, Depends, Query

from api.database import get_mongo_db
from api.security import require_permission
from api.services.analytics import _query, _query_one
from api.services.clickhouse_resilience import execute_clickhouse
from api.services.health import dependency_health

router = APIRouter(prefix="/admin", tags=["Admin Dashboard"])


@router.post("/mock/social")
def inject_mock_social_posts(
    count: int = Query(default=10, ge=1, le=1000),
    user: dict = Depends(require_permission("mock_data.create")),
):
    """Insert synthetic social posts for local/demo alert testing."""
    del user
    sources = ("reddit_vn", "facebook", "voz_forum", "youtube_comments")
    topics = (
        "AI và tương lai việc làm",
        "Thị trường công nghệ hôm nay",
        "Cộng đồng bàn luận về sản phẩm mới",
        "Xu hướng nổi bật trên mạng xã hội",
    )
    sentiments = ("positive", "neutral", "negative")
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    rows = []
    for _ in range(count):
        post_id = f"live_post_{uuid4().hex}"
        source = choice(sources)
        title = choice(topics)
        rows.append([
            post_id,
            source,
            title,
            f"Synthetic demo post about {title.lower()}.",
            randint(20, 500),
            round(uniform(0.75, 1.0), 4),
            randint(5, 180),
            round(uniform(-1.0, 1.0), 4),
            choice(sentiments),
            now,
            now,
            now,
        ])

    execute_clickhouse(
        lambda client: client.insert(
            "newspulse.social_sentiment_metrics",
            rows,
            column_names=[
                "post_id", "source", "title", "content", "like_count",
                "upvote_ratio", "reply_count", "sentiment_score",
                "sentiment_label", "publish_time", "crawled_at", "loaded_at",
            ],
        )
    )

    return {
        "status": "success",
        "count": count,
        "synthetic": True,
        "message": f"Injected {count} synthetic social posts",
    }


@router.get("/metrics/latency")
def get_crawl_latency(user: dict = Depends(require_permission("system.read"))):
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
def get_article_volume(user: dict = Depends(require_permission("system.read"))):
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
async def get_user_metrics(user: dict = Depends(require_permission("system.read"))):
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
async def get_system_health(user: dict = Depends(require_permission("system.read"))):
    result = await dependency_health()
    return {**result, "generated_at": datetime.now(timezone.utc).isoformat()}


@router.get("/metrics/operations")
def get_operations_metrics(user: dict = Depends(require_permission("system.read"))):
    """Return ingestion freshness and NLP coverage for the current article set."""
    row = _query_one("""
        SELECT
            (SELECT uniqExact(url_hash)
             FROM newspulse.raw_articles) AS total_articles,
            (SELECT uniqExact(url_hash)
             FROM newspulse.raw_articles
             WHERE loaded_at >= now() - INTERVAL 24 HOUR) AS articles_last_24h,
            (SELECT max(loaded_at)
             FROM newspulse.raw_articles) AS latest_loaded_at,
            (SELECT uniqExact(a.url_hash)
             FROM newspulse.raw_articles a
             INNER JOIN newspulse.raw_article_sentiment s
                 ON a.url_hash = s.url_hash) AS nlp_linked_articles
    """)

    total_articles = int(row.get("total_articles", 0) or 0)
    linked_articles = int(row.get("nlp_linked_articles", 0) or 0)
    latest_loaded_at = row.get("latest_loaded_at")
    freshness_minutes = None
    if latest_loaded_at:
        if latest_loaded_at.tzinfo is None:
            latest_loaded_at = latest_loaded_at.replace(tzinfo=timezone.utc)
        freshness_minutes = max(
            int((datetime.now(timezone.utc) - latest_loaded_at).total_seconds() // 60),
            0,
        )

    return {
        "articles_last_24h": int(row.get("articles_last_24h", 0) or 0),
        "total_articles": total_articles,
        "nlp_linked_articles": linked_articles,
        "nlp_coverage_pct": round(
            linked_articles * 100 / total_articles, 1
        ) if total_articles else 0.0,
        "latest_loaded_at": latest_loaded_at,
        "freshness_minutes": freshness_minutes,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
