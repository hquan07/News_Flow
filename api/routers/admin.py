from datetime import datetime, timezone
from random import randint, uniform
from typing import Literal
from uuid import uuid4

from fastapi import APIRouter, Depends, Query

from api.database import get_mongo_db
from api.security import require_permission
from api.services.analytics import _query, _query_one
from api.services.clickhouse_resilience import execute_clickhouse
from api.services.health import dependency_health

router = APIRouter(prefix="/admin", tags=["Admin Dashboard"])

MockScenario = Literal["balanced", "high_engagement", "negative_sentiment"]
MOCK_SCENARIOS = {
    "balanced": {
        "label": "Chart coverage",
        "description": "Balanced sources and sentiments with low engagement.",
        "sources": ("reddit_vn", "facebook", "voz_forum", "youtube_comments"),
        "sentiments": ("positive", "neutral", "negative"),
        "like_range": (2, 30),
        "reply_range": (0, 10),
        "topics": (
            "AI và tương lai việc làm",
            "Thị trường công nghệ hôm nay",
            "Cộng đồng bàn luận về sản phẩm mới",
            "Xu hướng nổi bật trên mạng xã hội",
        ),
    },
    "high_engagement": {
        "label": "High engagement",
        "description": "Posts with many likes and replies for engagement and viral-alert testing.",
        "sources": ("reddit_vn", "facebook", "voz_forum", "youtube_comments"),
        "sentiments": ("positive", "neutral", "negative"),
        "like_range": (1500, 6000),
        "reply_range": (200, 900),
        "topics": (
            "Chủ đề công nghệ đang được quan tâm",
            "Bài thảo luận thu hút nhiều tương tác",
            "Sự kiện nổi bật trong cộng đồng",
        ),
    },
    "negative_sentiment": {
        "label": "Negative sentiment",
        "description": "Negative posts concentrated on one source for sentiment and crisis-alert testing.",
        "sources": ("reddit_vn",),
        "sentiments": ("negative",),
        "like_range": (2, 30),
        "reply_range": (0, 10),
        "topics": (
            "Người dùng phản ánh lỗi dịch vụ",
            "Tranh cãi về chất lượng sản phẩm",
            "Cộng đồng bày tỏ sự thất vọng",
        ),
    },
}


@router.get("/mock/social/scenarios")
def list_mock_social_scenarios(
    _user: dict = Depends(require_permission("mock_data.create")),
):
    return {
        "scenarios": [
            {
                "id": key,
                "label": config["label"],
                "description": config["description"],
                "sources": config["sources"],
                "sentiments": config["sentiments"],
                "like_range": config["like_range"],
                "reply_range": config["reply_range"],
            }
            for key, config in MOCK_SCENARIOS.items()
        ],
        "destination": "newspulse.social_sentiment_metrics",
    }


@router.post("/mock/social")
def inject_mock_social_posts(
    count: int = Query(default=10, ge=1, le=1000),
    scenario: MockScenario = Query(default="balanced"),
    user: dict = Depends(require_permission("mock_data.create")),
):
    """Insert synthetic social posts for local/demo alert testing."""
    del user
    config = MOCK_SCENARIOS[scenario]
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    rows = []
    for index in range(count):
        post_id = f"live_post_{uuid4().hex}"
        source = config["sources"][index % len(config["sources"])]
        title = config["topics"][index % len(config["topics"])]
        sentiment = config["sentiments"][index % len(config["sentiments"])]
        if sentiment == "positive":
            sentiment_score = round(uniform(0.25, 0.9), 4)
        elif sentiment == "negative":
            sentiment_score = round(uniform(-0.95, -0.5), 4)
        else:
            sentiment_score = round(uniform(-0.15, 0.15), 4)
        rows.append([
            post_id,
            source,
            f"[MOCK] {title}",
            f"[MOCK:{scenario}] Synthetic demo post about {title.lower()}.",
            randint(*config["like_range"]),
            round(uniform(0.75, 1.0), 4),
            randint(*config["reply_range"]),
            sentiment_score,
            sentiment,
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
        "scenario": scenario,
        "synthetic": True,
        "message": f"Injected {count} synthetic social posts for {config['label']}",
    }


@router.get("/metrics/latency")
def get_crawl_latency(user: dict = Depends(require_permission("system.read"))):
    """Return operational crawl latency for articles published in the last hour."""
    query = """
        SELECT
            source,
            sum(crawl_latency_minutes) AS latency_sum,
            count() AS latency_count
        FROM newspulse.raw_articles FINAL
        WHERE publish_time >= now() - INTERVAL 60 MINUTE
          AND isFinite(crawl_latency_minutes)
          AND crawl_latency_minutes >= 0
        GROUP BY source
        ORDER BY latency_sum / latency_count DESC
    """
    df = _query(query)
    if not df:
        return {
            "sources": [],
            "avg_latency": [],
            "overall_average": 0,
            "sample_count": 0,
            "window_minutes": 60,
            "unit": "minutes",
            "sla_target": 5,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

    # Keep the overall value weighted by article count. Averaging the source
    # averages makes the KPI move when a small source is added or removed.
    total_latency = sum(float(row.get("latency_sum", 0) or 0) for row in df)
    total_samples = sum(int(row.get("latency_count", 0) or 0) for row in df)
    latencies = [
        round(
            float(row.get("latency_sum", 0) or 0)
            / int(row.get("latency_count", 0) or 1),
            2,
        )
        for row in df
    ]

    return {
        "sources": [row["source"] for row in df],
        "avg_latency": latencies,
        "overall_average": round(total_latency / total_samples, 2) if total_samples else 0,
        "sample_count": total_samples,
        "window_minutes": 60,
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
            uniqExact(a.url_hash) AS total_articles,
            uniqExactIf(a.url_hash, a.loaded_at >= now() - INTERVAL 24 HOUR)
                AS articles_last_24h,
            max(a.loaded_at) AS latest_loaded_at,
            uniqExactIf(a.url_hash, notEmpty(s.url_hash)) AS nlp_linked_articles
        FROM newspulse.raw_articles AS a FINAL
        LEFT ANY JOIN (
            SELECT url_hash
            FROM newspulse.raw_article_sentiment FINAL
            GROUP BY url_hash
        ) AS s USING (url_hash)
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
