"""Strict contracts for explicit, confirmed chatbot actions."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ActionPreviewRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    action: Literal["acknowledge_alert", "trigger_crawler", "generate_report"]
    alert_id: str | None = Field(default=None, max_length=80)
    spider_name: str | None = Field(default=None, max_length=80)
    time_range: Literal["today", "7d", "30d"] | None = None
    source: str | None = Field(default=None, max_length=80)

    @model_validator(mode="after")
    def validate_action_fields(self):
        if self.action == "acknowledge_alert":
            valid = bool(self.alert_id) and not (self.spider_name or self.time_range or self.source)
        elif self.action == "trigger_crawler":
            valid = bool(self.spider_name) and not (self.alert_id or self.time_range or self.source)
        else:
            valid = bool(self.time_range) and not (self.alert_id or self.spider_name)
        if not valid:
            raise ValueError("Invalid fields for selected action")
        return self


class ActionConfirmRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    action_id: str
    confirmation_token: str = Field(min_length=32, max_length=128)
    confirm: Literal[True]
