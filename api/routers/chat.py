"""Authenticated conversation and read-only news question endpoints."""

import asyncio
import json
import logging
from time import monotonic

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from fastapi.responses import StreamingResponse
from clickhouse_connect.driver.exceptions import DatabaseError

from api.models.chat import (
    ChatRequest,
    ChatResponse,
    ChatFeedback,
    ChatFeedbackRequest,
    Conversation,
    ConversationCreate,
    ConversationDetail,
    ConversationProjectUpdate,
    Project,
    ProjectCreate,
    ProjectUpdate,
)
from api.security import require_permission
from api.services import chat_guard, chat_metrics, chat_store, chat_tools


router = APIRouter(prefix="/chat", tags=["Chat"])
logger = logging.getLogger("newspulse.chat")


async def _record_metric(tool: str, outcome: str, started: float, source_count: int = 0) -> None:
    try:
        await chat_metrics.record(tool, outcome, monotonic() - started, source_count)
    except Exception:
        logger.exception("Unable to record chatbot metric")


async def _run_tool(
    payload: ChatRequest, actor: dict, previous_context: dict | None
) -> chat_tools.ToolResult:
    try:
        return await asyncio.to_thread(
            chat_tools.answer_question, payload, actor, previous_context
        )
    except DatabaseError as exc:
        logger.exception("Chat data query failed")
        raise HTTPException(status_code=500, detail="Chat data query failed") from exc


async def _answer(payload: ChatRequest, actor: dict) -> ChatResponse:
    started = monotonic()
    owner_id = actor["sub"]
    previous_context = None
    tool = "unknown"
    try:
        if payload.conversation_id:
            # Check ownership before executing a query or writing any messages.
            conversation = await chat_store.get_conversation(owner_id, payload.conversation_id)
            if payload.project_id is not None and payload.project_id != conversation["project_id"]:
                raise HTTPException(status_code=422, detail="Move conversation via the project endpoint")
            last_answer = next(
                (message for message in reversed(conversation["messages"])
                 if message["role"] == "assistant"),
                None,
            )
            previous_context = last_answer.get("context") if last_answer else None

        await chat_guard.check_rate_limit(owner_id)
        result = await _run_tool(payload, actor, previous_context)
        tool = result.tool or "none"
        if payload.conversation_id:
            conversation_id = payload.conversation_id
        else:
            conversation = await chat_store.create_conversation(
                owner_id, payload.message.strip()[:120], project_id=payload.project_id
            )
            conversation_id = conversation["id"]

        await chat_store.append_message(owner_id, conversation_id, "user", payload.message)
        assistant_message = await chat_store.append_message(
            owner_id,
            conversation_id,
            "assistant",
            result.answer,
            sources=result.sources,
            tool=result.tool,
            queried_at=result.queried_at,
            chart=result.chart,
            context=result.context,
        )
        response = ChatResponse(
            conversation_id=conversation_id,
            message_id=assistant_message["id"],
            answer=result.answer,
            tool=result.tool,
            sources=result.sources,
            queried_at=result.queried_at,
            time_range=result.time_range,
            chart=result.chart,
            context=result.context,
        )
    except HTTPException as exc:
        outcome = "rate_limited" if exc.status_code == 429 else "denied" if exc.status_code in (401, 403, 404) else "errors"
        await _record_metric(tool, outcome, started)
        raise
    except Exception:
        await _record_metric(tool, "errors", started)
        raise
    await _record_metric(tool, "success", started, len(result.sources))
    return response


@router.post("", response_model=ChatResponse)
async def ask_chat(
    payload: ChatRequest,
    actor: dict = Depends(require_permission("chat.use")),
):
    return await _answer(payload, actor)


@router.post("/stream")
async def stream_chat(
    payload: ChatRequest,
    actor: dict = Depends(require_permission("chat.use")),
):
    result = await _answer(payload, actor)

    async def events():
        for offset in range(0, len(result.answer), 200):
            chunk = result.answer[offset:offset + 200]
            yield f"event: delta\ndata: {json.dumps({'text': chunk}, ensure_ascii=False)}\n\n"
        metadata = result.model_dump(mode="json", exclude={"answer"})
        yield f"event: done\ndata: {json.dumps(metadata, ensure_ascii=False)}\n\n"

    return StreamingResponse(events(), media_type="text/event-stream", headers={
        "Cache-Control": "no-cache",
        "X-Accel-Buffering": "no",
    })


@router.put("/conversations/{conversation_id}/messages/{message_id}/feedback", response_model=ChatFeedback)
async def save_message_feedback(
    conversation_id: str,
    message_id: str,
    payload: ChatFeedbackRequest,
    actor: dict = Depends(require_permission("chat.use")),
):
    await chat_guard.check_rate_limit(actor["sub"])
    return await chat_store.set_message_feedback(actor["sub"], conversation_id, message_id, payload.reason)


@router.get("/feedback/summary")
async def get_feedback_summary(
    days: int = Query(default=7, ge=1, le=90),
    _actor: dict = Depends(require_permission("system.read")),
):
    return await chat_store.feedback_summary(days)


@router.post("/conversations", response_model=Conversation, status_code=status.HTTP_201_CREATED)
async def create_conversation(
    payload: ConversationCreate,
    actor: dict = Depends(require_permission("chat.use")),
):
    return await chat_store.create_conversation(actor["sub"], payload.title, payload.project_id)


@router.post("/projects", response_model=Project, status_code=status.HTTP_201_CREATED)
async def create_project(
    payload: ProjectCreate,
    actor: dict = Depends(require_permission("chat.use")),
):
    return await chat_store.create_project(actor["sub"], payload.title)


@router.get("/projects", response_model=list[Project])
async def list_projects(actor: dict = Depends(require_permission("chat.use"))):
    return await chat_store.list_projects(actor["sub"])


@router.patch("/projects/{project_id}", response_model=Project)
async def rename_project(
    project_id: str,
    payload: ProjectUpdate,
    actor: dict = Depends(require_permission("chat.use")),
):
    return await chat_store.rename_project(actor["sub"], project_id, payload.title)


@router.delete("/projects/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_project(
    project_id: str,
    actor: dict = Depends(require_permission("chat.use")),
):
    await chat_store.delete_project(actor["sub"], project_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/metrics")
async def get_chat_metrics(
    hours: int = Query(default=24, ge=1, le=168),
    _actor: dict = Depends(require_permission("system.read")),
):
    return await chat_metrics.snapshot(hours)


@router.get("/conversations", response_model=list[Conversation])
async def list_conversations(
    limit: int = Query(default=50, ge=1, le=100),
    project_id: str | None = Query(default=None),
    q: str | None = Query(default=None, max_length=120),
    actor: dict = Depends(require_permission("chat.use")),
):
    return await chat_store.list_conversations(actor["sub"], limit, project_id, q)


@router.get("/conversations/{conversation_id}", response_model=ConversationDetail)
async def get_conversation(
    conversation_id: str,
    actor: dict = Depends(require_permission("chat.use")),
):
    return await chat_store.get_conversation(actor["sub"], conversation_id)


@router.patch("/conversations/{conversation_id}/project", response_model=Conversation)
async def move_conversation(
    conversation_id: str,
    payload: ConversationProjectUpdate,
    actor: dict = Depends(require_permission("chat.use")),
):
    return await chat_store.move_conversation(actor["sub"], conversation_id, payload.project_id)


@router.delete("/conversations/{conversation_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_conversation(
    conversation_id: str,
    actor: dict = Depends(require_permission("chat.use")),
):
    await chat_store.delete_conversation(actor["sub"], conversation_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
