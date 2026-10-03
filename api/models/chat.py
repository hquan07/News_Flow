"""Contracts for the chatbot's persisted conversations."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator


class ConversationCreate(BaseModel):
    title: str = Field(default="New conversation", min_length=1, max_length=120)
    project_id: str | None = None


class ProjectCreate(BaseModel):
    title: str = Field(min_length=1, max_length=80)

    @field_validator("title")
    @classmethod
    def clean_title(cls, value: str) -> str:
        title = " ".join(value.split())
        if not title:
            raise ValueError("Project title cannot be blank")
        return title


class ProjectUpdate(ProjectCreate):
    pass


class Project(BaseModel):
    id: str
    title: str
    created_at: datetime
    updated_at: datetime


class ConversationProjectUpdate(BaseModel):
    project_id: str | None


class Conversation(BaseModel):
    id: str
    title: str
    project_id: str | None = None
    created_at: datetime
    updated_at: datetime


class ChatMessage(BaseModel):
    id: str
    conversation_id: str
    role: Literal["user", "assistant"]
    content: str
    created_at: datetime
    sources: list["ChatSource"] = Field(default_factory=list)
    tool: str | None = None
    queried_at: datetime | None = None
    chart: "ChatChart | None" = None
    context: "ChatContext | None" = None
    feedback: "ChatFeedback | None" = None


class ChatFeedbackRequest(BaseModel):
    reason: Literal["helpful", "wrong_source", "wrong_number"]


class ChatFeedback(ChatFeedbackRequest):
    updated_at: datetime | None = None


class ChatSource(BaseModel):
    article_id: str
    title: str
    url: str
    source: str
    published_at: datetime | None = None


class ChatChartPoint(BaseModel):
    label: str
    value: float


class ChatChart(BaseModel):
    type: Literal["bar"] = "bar"
    title: str
    unit: str
    points: list[ChatChartPoint] = Field(default_factory=list)


class ChatContext(BaseModel):
    intent: str
    time_range: Literal["today", "7d", "30d", "all"] | None = None
    source: str | None = None
    compare_sources: list[str] | None = None
    category: str | None = None
    query: str | None = None
    clarification: bool = False
    event_id: str | None = None
    watchlist_id: str | None = None


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=2000)
    conversation_id: str | None = None
    project_id: str | None = None
    time_range: Literal["today", "7d", "30d"] | None = None
    source: str | None = Field(default=None, max_length=80)
    category: str | None = Field(default=None, max_length=80)
    query: str | None = Field(default=None, max_length=120)
    compare_sources: list[str] | None = Field(default=None, min_length=2, max_length=6)
    event_id: str | None = Field(default=None, max_length=64)
    watchlist_id: str | None = Field(default=None, max_length=64)

    @field_validator("message")
    @classmethod
    def nonempty_message(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Message cannot be blank")
        return value


class ChatResponse(BaseModel):
    conversation_id: str
    message_id: str | None = None
    answer: str
    tool: str | None = None
    sources: list[ChatSource] = Field(default_factory=list)
    queried_at: datetime | None = None
    time_range: str | None = None
    chart: ChatChart | None = None
    context: ChatContext | None = None


class ConversationDetail(Conversation):
    messages: list[ChatMessage] = Field(default_factory=list)
