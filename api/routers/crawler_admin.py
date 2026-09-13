"""
Crawler Management API — Proxy to Airflow REST API.
Allows Admin to view crawler statuses, trigger crawls, and check data quality.
"""
import httpx
import logging
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query
from typing import Optional
from api.routers.admin import get_admin_user
from api.services.analytics import _query

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin/crawlers", tags=["Crawler Management"])

# Airflow REST API config (internal Docker network)
AIRFLOW_BASE_URL = "http://airflow-webserver:8080/api/v1"
AIRFLOW_AUTH = ("admin", "admin")

# Map spider name -> readable info
SPIDER_REGISTRY = {
    "vnexpress":        {"type": "news",   "label": "VnExpress",        "schedule": "*/30 * * * *"},
    "tuoitre":          {"type": "news",   "label": "Tuổi Trẻ",         "schedule": "*/30 * * * *"},
    "thanhnien":        {"type": "news",   "label": "Thanh Niên",       "schedule": "*/30 * * * *"},
    "tienphong":        {"type": "news",   "label": "Tiền Phong",       "schedule": "*/30 * * * *"},
    "dantri":           {"type": "news",   "label": "Dân Trí",          "schedule": "*/30 * * * *"},
    "laodong":          {"type": "news",   "label": "Lao Động",         "schedule": "*/30 * * * *"},
    "voz_forum":        {"type": "social", "label": "Voz Forum",        "schedule": "*/30 * * * *"},
    "reddit_vn":        {"type": "social", "label": "Reddit Vietnam",   "schedule": "*/30 * * * *"},
    "youtube_comments": {"type": "social", "label": "YouTube Comments", "schedule": "*/30 * * * *"},
}


async def _airflow_get(path: str) -> dict:
    """Helper to call Airflow REST API with basic auth."""
    async with httpx.AsyncClient(timeout=15.0) as client:
        try:
            resp = await client.get(f"{AIRFLOW_BASE_URL}{path}", auth=AIRFLOW_AUTH)
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPStatusError as e:
            logger.error(f"Airflow API error: {e.response.status_code} - {e.response.text}")
            raise HTTPException(status_code=502, detail=f"Airflow API error: {e.response.status_code}")
        except httpx.ConnectError:
            logger.error("Cannot connect to Airflow webserver")
            raise HTTPException(status_code=503, detail="Airflow webserver is not reachable")


async def _airflow_post(path: str, json_body: dict = None) -> dict:
    """Helper to POST to Airflow REST API."""
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            resp = await client.post(
                f"{AIRFLOW_BASE_URL}{path}",
                auth=AIRFLOW_AUTH,
                json=json_body or {},
            )
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPStatusError as e:
            logger.error(f"Airflow API error: {e.response.status_code} - {e.response.text}")
            raise HTTPException(status_code=502, detail=f"Airflow API error: {e.response.status_code}")
        except httpx.ConnectError:
            raise HTTPException(status_code=503, detail="Airflow webserver is not reachable")


@router.get("/")
async def list_crawlers(user: dict = Depends(get_admin_user)):
    """
    Trả về danh sách tất cả crawler spiders cùng trạng thái chạy cuối cùng từ Airflow.
    """
    # Get latest DAG runs for crawl DAG
    try:
        dag_runs_data = await _airflow_get(
            "/dags/newspulse_crawl/dagRuns?order_by=-execution_date&limit=1"
        )
        latest_run = dag_runs_data.get("dag_runs", [{}])[0] if dag_runs_data.get("dag_runs") else {}

        # Get task instances for the latest run
        task_instances = {}
        if latest_run.get("dag_run_id"):
            run_id = latest_run["dag_run_id"]
            tasks_data = await _airflow_get(
                f"/dags/newspulse_crawl/dagRuns/{run_id}/taskInstances"
            )
            for ti in tasks_data.get("task_instances", []):
                task_instances[ti["task_id"]] = {
                    "state": ti.get("state", "unknown"),
                    "start_date": ti.get("start_date"),
                    "end_date": ti.get("end_date"),
                    "duration": ti.get("duration"),
                    "try_number": ti.get("try_number"),
                }
    except HTTPException:
        # Airflow unreachable — return registry with unknown statuses
        latest_run = {}
        task_instances = {}

    # Build response per spider
    crawlers = []
    for spider_name, info in SPIDER_REGISTRY.items():
        task_id = f"crawl_{spider_name}"
        ti = task_instances.get(task_id, {})

        crawlers.append({
            "spider_name": spider_name,
            "label": info["label"],
            "type": info["type"],
            "schedule": info["schedule"],
            "last_state": ti.get("state", "no_run"),
            "last_start": ti.get("start_date"),
            "last_end": ti.get("end_date"),
            "duration_sec": round(ti.get("duration", 0) or 0, 1),
            "try_number": ti.get("try_number", 0),
        })

    # Get article counts per source from ClickHouse
    try:
        news_counts = _query(
            "SELECT source, count() as cnt FROM newspulse.raw_articles GROUP BY source"
        )
        social_counts = _query(
            "SELECT source, count() as cnt FROM newspulse.social_sentiment_metrics GROUP BY source"
        )
        count_map = {}
        # Mapping from ClickHouse source to spider name
        source_mapping = {
            "voz": "voz_forum",
            "reddit": "reddit_vn",
            "youtube": "youtube_comments",
            # Add news source mapping if they differ, though usually they match.
            # e.g., "vnexpress" -> "vnexpress"
        }
        for row in (news_counts or []):
            count_map[row["source"]] = int(row["cnt"])
        for row in (social_counts or []):
            mapped_source = source_mapping.get(row["source"], row["source"])
            count_map[mapped_source] = int(row["cnt"])
    except Exception:
        count_map = {}

    for c in crawlers:
        c["total_items"] = count_map.get(c["spider_name"], 0)

    return {
        "crawlers": crawlers,
        "dag_state": latest_run.get("state", "unknown"),
        "dag_run_id": latest_run.get("dag_run_id"),
        "dag_execution_date": latest_run.get("execution_date"),
    }


@router.post("/trigger/{spider_name}")
async def trigger_crawler(spider_name: str, user: dict = Depends(get_admin_user)):
    """
    Trigger cào dữ liệu cho 1 spider cụ thể bằng cách gọi Airflow REST API.
    Sử dụng conf parameter để chỉ định spider (nếu DAG hỗ trợ),
    hoặc trigger toàn bộ DAG crawl.
    """
    if spider_name not in SPIDER_REGISTRY and spider_name != "all":
        raise HTTPException(status_code=404, detail=f"Spider '{spider_name}' not found")

    run_id = f"manual__{spider_name}__{datetime.utcnow().strftime('%Y%m%dT%H%M%S')}"

    result = await _airflow_post(
        "/dags/newspulse_crawl/dagRuns",
        json_body={
            "dag_run_id": run_id,
            "conf": {"spider": spider_name},
            "note": f"Triggered by admin via UI for spider: {spider_name}",
        }
    )

    return {
        "message": f"Crawler '{spider_name}' triggered successfully",
        "dag_run_id": result.get("dag_run_id"),
        "state": result.get("state"),
        "execution_date": result.get("execution_date"),
    }


@router.get("/history")
async def crawler_history(
    limit: int = Query(10, ge=1, le=50),
    user: dict = Depends(get_admin_user),
):
    """Lấy lịch sử các DAG run gần nhất."""
    data = await _airflow_get(
        f"/dags/newspulse_crawl/dagRuns?order_by=-execution_date&limit={limit}"
    )

    runs = []
    for run in data.get("dag_runs", []):
        runs.append({
            "dag_run_id": run.get("dag_run_id"),
            "state": run.get("state"),
            "execution_date": run.get("execution_date"),
            "start_date": run.get("start_date"),
            "end_date": run.get("end_date"),
            "note": run.get("note"),
        })

    return {"runs": runs}


@router.get("/data-quality")
async def data_quality_summary(user: dict = Depends(get_admin_user)):
    """
    Thống kê chất lượng dữ liệu: tỷ lệ bài viết thiếu author, thiếu content, v.v.
    """
    try:
        # News articles quality
        news_quality = _query("""
            SELECT
                count() as total,
                countIf(author = '' OR author IS NULL) as missing_author,
                countIf(content = '' OR content IS NULL) as missing_content,
                countIf(length(content) < 50) as short_content,
                countIf(category = '' OR category IS NULL) as missing_category
            FROM newspulse.raw_articles
        """)

        # Social posts quality 
        social_quality = _query("""
            SELECT
                count() as total,
                countIf(title = '' OR title IS NULL) as missing_title,
                countIf(content = '' OR content IS NULL) as missing_content,
                countIf(source = '' OR source IS NULL) as missing_source
            FROM newspulse.social_sentiment_metrics
        """)

        news_row = news_quality[0] if news_quality else {}
        social_row = social_quality[0] if social_quality else {}

        news_total = int(news_row.get("total", 0)) or 1
        social_total = int(social_row.get("total", 0)) or 1

        return {
            "news": {
                "total": int(news_row.get("total", 0)),
                "missing_author": int(news_row.get("missing_author", 0)),
                "missing_author_pct": round(int(news_row.get("missing_author", 0)) / news_total * 100, 1),
                "missing_content": int(news_row.get("missing_content", 0)),
                "missing_content_pct": round(int(news_row.get("missing_content", 0)) / news_total * 100, 1),
                "short_content": int(news_row.get("short_content", 0)),
                "short_content_pct": round(int(news_row.get("short_content", 0)) / news_total * 100, 1),
                "missing_category": int(news_row.get("missing_category", 0)),
                "missing_category_pct": round(int(news_row.get("missing_category", 0)) / news_total * 100, 1),
            },
            "social": {
                "total": int(social_row.get("total", 0)),
                "missing_title": int(social_row.get("missing_title", 0)),
                "missing_title_pct": round(int(social_row.get("missing_title", 0)) / social_total * 100, 1),
                "missing_content": int(social_row.get("missing_content", 0)),
                "missing_content_pct": round(int(social_row.get("missing_content", 0)) / social_total * 100, 1),
                "missing_source": int(social_row.get("missing_source", 0)),
                "missing_source_pct": round(int(social_row.get("missing_source", 0)) / social_total * 100, 1),
            },
        }
    except Exception as e:
        logger.error(f"Data quality query error: {e}")
        return {"news": {}, "social": {}}
