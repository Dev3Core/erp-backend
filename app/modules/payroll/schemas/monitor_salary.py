import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class MonitorSalaryCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    monitor_id: uuid.UUID
    amount_cop: Decimal = Field(gt=0, decimal_places=2)
    effective_from: date
    notes: str | None = Field(default=None, max_length=2000)


class MonitorSalaryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    monitor_id: uuid.UUID
    amount_cop: Decimal
    effective_from: date
    notes: str | None
    created_at: datetime


class MonitorSalaryListResponse(BaseModel):
    items: list[MonitorSalaryResponse]
    total: int


class CurrentSalaryResponse(BaseModel):
    monitor_id: uuid.UUID
    amount_cop: Decimal
    effective_from: date
