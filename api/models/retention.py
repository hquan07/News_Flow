from pydantic import BaseModel, Field, model_validator


class RetentionPolicyUpdate(BaseModel):
    retention_days: int = Field(ge=7, le=3650)
    enabled: bool = True


class RetentionApply(BaseModel):
    confirm: bool

    @model_validator(mode="after")
    def require_confirmation(self):
        if self.confirm is not True:
            raise ValueError("Explicit confirmation is required")
        return self
