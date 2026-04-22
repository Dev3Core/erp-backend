import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, HttpUrl

from app.models.room import Platform, RoomStatus


class RoomCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=2, max_length=255)
    platform: Platform
    url: HttpUrl


class RoomUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=2, max_length=255)
    url: HttpUrl | None = None
    status: RoomStatus | None = None
    is_active: bool | None = None


class RoomResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    platform: Platform
    url: str
    status: RoomStatus
    is_active: bool
    created_at: datetime


class RoomListResponse(BaseModel):
    items: list[RoomResponse]
    total: int
