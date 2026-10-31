"""Request/response schemas for /settings (SDD Table 3.3)."""
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class SettingResponse(BaseModel):
    """One row of the setting table."""

    model_config = ConfigDict(from_attributes=True)

    key: str
    value: str
    description: str | None
    updated_at: datetime


class SettingUpdateRequest(BaseModel):
    """Body for PATCH /settings/{key}."""

    value: str = Field(min_length=1, max_length=500)