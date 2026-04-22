import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.shift import ShiftStatus


class ShiftCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    model_id: uuid.UUID
    room_id: uuid.UUID
    monitor_id: uuid.UUID | None = None
    start_time: datetime
    end_time: datetime | None = None

    @model_validator(mode="after")
    def _end_after_start(self) -> "ShiftCreate":
        if self.end_time is not None and self.end_time <= self.start_time:
            raise ValueError("end_time must be after start_time")
        return self


class ShiftUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    monitor_id: uuid.UUID | None = None
    status: ShiftStatus | None = None
    start_time: datetime | None = None
    end_time: datetime | None = None
    tokens_earned: int | None = Field(default=None, ge=0)
    usd_earned: Decimal | None = Field(default=None, ge=0, decimal_places=2)

    @model_validator(mode="after")
    def _end_after_start(self) -> "ShiftUpdate":
        if (
            self.start_time is not None
            and self.end_time is not None
            and self.end_time <= self.start_time
        ):
            raise ValueError("end_time must be after start_time")
        return self


class ShiftResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    model_id: uuid.UUID
    room_id: uuid.UUID
    monitor_id: uuid.UUID | None
    status: ShiftStatus
    start_time: datetime
    end_time: datetime | None
    tokens_earned: int
    usd_earned: Decimal
    created_at: datetime


class ShiftListResponse(BaseModel):
    items: list[ShiftResponse]
    total: int
