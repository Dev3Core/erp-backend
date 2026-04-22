import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.models.salary_advance_request import SalaryAdvanceStatus


class SalaryAdvanceRequestCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    amount_cop: Decimal = Field(gt=0, decimal_places=2)
    reason: str | None = Field(default=None, max_length=2000)


class SalaryAdvanceRequestReview(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: SalaryAdvanceStatus
    review_notes: str | None = Field(default=None, max_length=2000)


class SalaryAdvanceRequestResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    requester_id: uuid.UUID
    amount_cop: Decimal
    reason: str | None
    status: SalaryAdvanceStatus
    reviewer_id: uuid.UUID | None
    reviewed_at: datetime | None
    review_notes: str | None
    created_at: datetime


class SalaryAdvanceRequestListResponse(BaseModel):
    items: list[SalaryAdvanceRequestResponse]
    total: int
