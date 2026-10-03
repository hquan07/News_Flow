from fastapi import APIRouter, Depends, Query, Response, status

from api.security import require_permission
from api.services import briefing_service, scheduled_reports


router = APIRouter(prefix="/briefings", tags=["Briefings & Reports"])


@router.get("/events/{event_id}")
def event_briefing(event_id: str):
    return briefing_service.event_briefing(event_id)


@router.post("/reports/from-query/{saved_query_id}", status_code=status.HTTP_201_CREATED)
async def generate_report(saved_query_id: str, actor: dict = Depends(require_permission("reports.export"))):
    return await scheduled_reports.generate(actor["sub"], saved_query_id)


@router.get("/reports")
async def reports(actor: dict = Depends(require_permission("reports.export"))):
    return await scheduled_reports.list_reports(actor["sub"])


@router.get("/reports/{report_id}")
async def report(report_id: str, actor: dict = Depends(require_permission("reports.export"))):
    return await scheduled_reports.get_report(actor["sub"], report_id)


@router.delete("/reports/{report_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_report(report_id: str, actor: dict = Depends(require_permission("reports.export"))):
    await scheduled_reports.delete_report(actor["sub"], report_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/reports/run-due")
async def run_due(limit: int = Query(default=50, ge=1, le=100), _actor: dict = Depends(require_permission("system.read"))):
    return await scheduled_reports.run_due(limit)
