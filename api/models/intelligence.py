"""Contracts for personal intelligence configuration."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator


class WatchlistCreate(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    kind: Literal["keyword", "entity", "source", "topic"]
    value: str = Field(min_length=1, max_length=160)
    enabled: bool = True

    @field_validator("name", "value")
    @classmethod
    def clean_text(cls, value: str) -> str:
        cleaned = " ".join(value.split())
        if not cleaned:
            raise ValueError("Value cannot be blank")
        return cleaned


class WatchlistUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=80)
    value: str | None = Field(default=None, min_length=1, max_length=160)
    enabled: bool | None = None

    @field_validator("name", "value")
    @classmethod
    def clean_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = " ".join(value.split())
        if not cleaned:
            raise ValueError("Value cannot be blank")
        return cleaned


class Watchlist(WatchlistCreate):
    id: str
    created_at: datetime
    updated_at: datetime


class AlertRuleCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    kind: Literal["keyword_volume", "negative_sentiment", "entity_mention"]
    target: str = Field(min_length=1, max_length=160)
    threshold: float = Field(gt=0, le=1_000_000)
    window_minutes: int = Field(default=60, ge=5, le=10_080)
    channels: list[Literal["dashboard", "telegram", "email", "webhook"]] = Field(
        default_factory=lambda: ["dashboard"], min_length=1, max_length=4
    )
    enabled: bool = True

    @field_validator("name", "target")
    @classmethod
    def clean_rule_text(cls, value: str) -> str:
        cleaned = " ".join(value.split())
        if not cleaned:
            raise ValueError("Value cannot be blank")
        return cleaned


class AlertRuleUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    target: str | None = Field(default=None, min_length=1, max_length=160)
    threshold: float | None = Field(default=None, gt=0, le=1_000_000)
    window_minutes: int | None = Field(default=None, ge=5, le=10_080)
    channels: list[Literal["dashboard", "telegram", "email", "webhook"]] | None = Field(
        default=None, min_length=1, max_length=4
    )
    enabled: bool | None = None


class AlertRule(AlertRuleCreate):
    id: str
    created_at: datetime
    updated_at: datetime


class SavedQueryCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    query: str = Field(default="", max_length=240)
    source: str | None = Field(default=None, max_length=80)
    category: str | None = Field(default=None, max_length=80)
    entity: str | None = Field(default=None, max_length=160)
    keyword: str | None = Field(default=None, max_length=160)
    sentiment: Literal["positive", "neutral", "negative"] | None = None
    schedule: Literal["none", "daily", "weekly", "monthly"] = "none"
    enabled: bool = True

    @field_validator("name")
    @classmethod
    def clean_name(cls, value: str) -> str:
        cleaned = " ".join(value.split())
        if not cleaned:
            raise ValueError("Name cannot be blank")
        return cleaned

    @model_validator(mode="after")
    def require_filter(self):
        if not any((self.query.strip(), self.source, self.category, self.entity, self.keyword)):
            raise ValueError("At least one search criterion is required")
        return self


class SavedQueryUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    schedule: Literal["none", "daily", "weekly", "monthly"] | None = None
    enabled: bool | None = None


class SavedQuery(SavedQueryCreate):
    id: str
    created_at: datetime
    updated_at: datetime
    next_run_at: datetime | None = None
