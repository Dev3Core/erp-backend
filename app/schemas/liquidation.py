import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.models.liquidation import LiquidationStatus


class LiquidationCreateFromShift(BaseModel):
    model_config = ConfigDict(extra="forbid")

    shift_id: uuid.UUID
    split_config_id: uuid.UUID | None = Field(
        default=None,
        description="Optional split to apply. If omitted, the tenant's default split is used.",
    )
    period_date: date | None = Field(
        default=None,
        description="Defaults to today if omitted.",
    )
    notes: str | None = Field(default=None, max_length=2000)


class LiquidationUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: LiquidationStatus | None = None
    notes: str | None = Field(default=None, max_length=2000)


class LiquidationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    shift_id: uuid.UUID
    period_date: date
    gross_usd: Decimal
    net_usd: Decimal
    cop_amount: Decimal
    trm_used: Decimal
    status: LiquidationStatus
    notes: str | None
    created_at: datetime


class LiquidationListResponse(BaseModel):
    items: list[LiquidationResponse]
    total: int
