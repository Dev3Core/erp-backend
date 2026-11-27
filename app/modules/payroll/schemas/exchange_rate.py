import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class ExchangeRateResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    rate_date: date
    cop_per_usd: Decimal
    source: str
    created_at: datetime


class ExchangeRateCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    rate_date: date
    cop_per_usd: Decimal = Field(gt=0, decimal_places=2)
    source: str = Field(default="manual", min_length=1, max_length=255)
