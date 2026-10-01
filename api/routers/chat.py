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
    Conversation,
    ConversationCreate,
    ConversationDetail,
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
                owner_id, payload.message.strip()[:120]
            )
            conversation_id = conversation["id"]

        await chat_store.append_message(owner_id, conversation_id, "user", payload.message)
        await chat_store.append_message(
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
            answer=result.answer,
            tool=result.tool,
            sources=result.sources,
            queried_at=result.queried_at,
            time_range=result.time_range,
            chart=result.chart,
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


@router.post("/conversations", response_model=Conversation, status_code=status.HTTP_201_CREATED)
async def create_conversation(
    payload: ConversationCreate,
    actor: dict = Depends(require_permission("chat.use")),
):
    return await chat_store.create_conversation(actor["sub"], payload.title)


@router.get("/metrics")
async def get_chat_metrics(
    hours: int = Query(default=24, ge=1, le=168),
    _actor: dict = Depends(require_permission("system.read")),
):
    return await chat_metrics.snapshot(hours)


@router.get("/conversations", response_model=list[Conversation])
async def list_conversations(
    limit: int = Query(default=50, ge=1, le=100),
    actor: dict = Depends(require_permission("chat.use")),
):
    return await chat_store.list_conversations(actor["sub"], limit)


@router.get("/conversations/{conversation_id}", response_model=ConversationDetail)
async def get_conversation(
    conversation_id: str,
    actor: dict = Depends(require_permission("chat.use")),
):
    return await chat_store.get_conversation(actor["sub"], conversation_id)


@router.delete("/conversations/{conversation_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_conversation(
    conversation_id: str,
    actor: dict = Depends(require_permission("chat.use")),
):
    await chat_store.delete_conversation(actor["sub"], conversation_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
