"""Conversation management endpoints; model responses arrive in a later phase."""

from fastapi import APIRouter, Depends, Query, Response, status

from api.models.chat import Conversation, ConversationCreate, ConversationDetail
from api.security import require_permission
from api.services import chat_store


router = APIRouter(prefix="/chat", tags=["Chat"])


@router.post("/conversations", response_model=Conversation, status_code=status.HTTP_201_CREATED)
async def create_conversation(
    payload: ConversationCreate,
    actor: dict = Depends(require_permission("chat.use")),
):
    return await chat_store.create_conversation(actor["sub"], payload.title)


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
