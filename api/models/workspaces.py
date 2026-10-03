from typing import Literal

from pydantic import BaseModel, EmailStr, Field, field_validator


class WorkspaceCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)

    @field_validator("name")
    @classmethod
    def clean_name(cls, value: str) -> str:
        value = " ".join(value.split())
        if not value:
            raise ValueError("Workspace name cannot be blank")
        return value


class WorkspaceMemberUpsert(BaseModel):
    email: EmailStr
    role: Literal["viewer", "editor"] = "viewer"


class SharedWatchlistCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    kind: Literal["keyword", "entity", "source", "topic"]
    value: str = Field(min_length=1, max_length=160)
