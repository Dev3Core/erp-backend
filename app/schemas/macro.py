import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.room import Platform


class MacroCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    label: str = Field(min_length=1, max_length=100)
    content: str = Field(min_length=1, max_length=5000)
    platform: Platform | None = None
    position: int = Field(default=0, ge=0)


class MacroUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    label: str | None = Field(default=None, min_length=1, max_length=100)
    content: str | None = Field(default=None, min_length=1, max_length=5000)
    platform: Platform | None = None
    position: int | None = Field(default=None, ge=0)
    is_active: bool | None = None


class MacroResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    label: str
    content: str
    platform: Platform | None
    position: int
    is_active: bool
    created_at: datetime


class MacroListResponse(BaseModel):
    items: list[MacroResponse]
    total: int
