import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict


class ShiftReportResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    shift_id: uuid.UUID
    duration_minutes: int
    total_tokens: int
    total_usd: Decimal
    summary: str | None
    created_at: datetime


class ShiftReportListResponse(BaseModel):
    items: list[ShiftReportResponse]
    total: int
