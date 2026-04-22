import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.room import Platform


class TagCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    room_id: uuid.UUID
    value: str = Field(min_length=1, max_length=80, pattern=r"^[a-zA-Z0-9_-]+$")
    platform: Platform


class TagUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    is_active: bool | None = None


class TagResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    room_id: uuid.UUID
    value: str
    platform: Platform
    is_active: bool
    last_applied_at: datetime | None
    created_at: datetime


class TagListResponse(BaseModel):
    items: list[TagResponse]
    total: int
