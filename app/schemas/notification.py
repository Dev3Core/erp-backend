import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.notification import NotificationKind


class NotificationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    kind: NotificationKind
    title: str
    body: str | None
    read_at: datetime | None
    meta: dict | None
    created_at: datetime


class NotificationMarkRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ids: list[uuid.UUID] = Field(min_length=1)
