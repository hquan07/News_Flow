from datetime import datetime, timezone

from fastapi import APIRouter, Depends

from api.routers import crawler_admin
from api.security import require_permission
from api.services import operations


router = APIRouter(prefix="/operations", tags=["Data Operations"])


@router.get("/lineage/{article_id}")
def lineage(article_id: str, _actor: dict = Depends(require_permission("system.read"))):
    return operations.article_lineage(article_id)


@router.post("/lineage/{article_id}/replay")
async def replay(article_id: str, actor: dict = Depends(require_permission("crawler.run"))):
    # Validate against the warehouse before scheduling a single-record replay.
    operations.replay_payload(article_id)
    run_id = f"replay__{article_id[:24]}__{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')}"
    result = await crawler_admin._airflow_post(
        "/dags/newspulse_article_replay/dagRuns",
        json_body={
            "dag_run_id": run_id,
            "conf": {"article_id": article_id},
            "note": f"Lineage replay requested by {actor['sub']}",
        },
    )
    return {"article_id": article_id, "dag_run_id": result.get("dag_run_id", run_id), "state": result.get("state", "queued")}
