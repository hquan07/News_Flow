from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator


class CrisisRoomCreate(BaseModel):
    event_id: str = Field(min_length=8, max_length=64)
    name: str = Field(min_length=1, max_length=120)
    notes: str = Field(default="", max_length=4000)

    @field_validator("name")
    @classmethod
    def clean_name(cls, value: str) -> str:
        value = " ".join(value.split())
        if not value:
            raise ValueError("Room name cannot be blank")
        return value


class CrisisRoomUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    notes: str | None = Field(default=None, max_length=4000)
    status: Literal["monitoring", "active", "resolved"] | None = None


class CrisisRoom(BaseModel):
    id: str
    event_id: str
    name: str
    notes: str
    status: Literal["monitoring", "active", "resolved"]
    event_snapshot: dict
    created_at: datetime
    updated_at: datetime
