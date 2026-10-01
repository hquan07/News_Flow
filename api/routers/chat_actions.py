"""Explicit preview/confirm endpoints for the chatbot's controlled actions."""

from fastapi import APIRouter, Depends, Response

from api.models.chat_actions import ActionConfirmRequest, ActionPreviewRequest
from api.security import require_permission
from api.services import chat_actions, chat_guard


router = APIRouter(prefix="/chat/actions", tags=["Chat Actions"])


@router.post("/preview")
async def preview_action(
    payload: ActionPreviewRequest,
    actor: dict = Depends(require_permission("chat.use")),
):
    await chat_guard.check_rate_limit(actor["sub"])
    return await chat_actions.preview(payload, actor)


@router.post("/confirm")
async def confirm_action(
    payload: ActionConfirmRequest,
    actor: dict = Depends(require_permission("chat.use")),
):
    await chat_guard.check_rate_limit(actor["sub"])
    return await chat_actions.confirm(payload, actor)


@router.get("/reports/{report_id}")
async def download_report(
    report_id: str,
    actor: dict = Depends(require_permission("chat.use")),
):
    csv_data = await chat_actions.report_csv(report_id, actor)
    return Response(
        content=csv_data,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="newspulse-report-{report_id}.csv"'},
    )


@router.get("/{action_id}")
async def get_action_status(
    action_id: str,
    actor: dict = Depends(require_permission("chat.use")),
):
    return await chat_actions.action_status(action_id, actor)
