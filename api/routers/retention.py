from datetime import datetime, timezone

from fastapi import APIRouter, Depends

from api.models.retention import RetentionApply, RetentionPolicyUpdate
from api.routers import crawler_admin
from api.security import require_permission
from api.services import retention


router = APIRouter(prefix="/operations/retention", tags=["Retention"])


@router.get("")
async def policies(_actor: dict = Depends(require_permission("system.read"))):
    return await retention.list_policies()


@router.put("/{dataset}")
async def update_policy(dataset: str, payload: RetentionPolicyUpdate, actor: dict = Depends(require_permission("crawler.run"))):
    return await retention.update_policy(dataset, payload.retention_days, payload.enabled, actor["sub"])


@router.get("/{dataset}/preview")
async def preview(dataset: str, _actor: dict = Depends(require_permission("system.read"))):
    return await retention.preview(dataset)


@router.post("/{dataset}/apply")
async def apply_policy(dataset: str, payload: RetentionApply, actor: dict = Depends(require_permission("crawler.run"))):
    result = await retention.preview(dataset)
    run_id = f"retention__{dataset}__{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')}"
    scheduled = await crawler_admin._airflow_post(
        "/dags/newspulse_retention/dagRuns",
        json_body={"dag_run_id": run_id, "conf": {"dataset": dataset}, "note": f"Confirmed by {actor['sub']}; preview rows={result['rows_to_delete']}"},
    )
    return {**result, "dag_run_id": scheduled.get("dag_run_id", run_id), "state": scheduled.get("state", "queued")}
