import uuid
from datetime import date
from decimal import Decimal

from pydantic import BaseModel, ConfigDict


class MetricsOverview(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    period_from: date | None = None
    period_to: date | None = None
    total_shifts: int
    total_tokens: int
    total_usd: Decimal
    total_cop_paid: Decimal
    liquidations_pending: int
    liquidations_approved: int
    liquidations_paid: int


class RevenueByModelItem(BaseModel):
    model_id: uuid.UUID
    email: str
    full_name: str
    total_shifts: int
    total_tokens: int
    total_usd: Decimal


class RevenueByMonitorItem(BaseModel):
    monitor_id: uuid.UUID | None
    email: str | None
    full_name: str | None
    total_shifts: int
    total_tokens: int
    total_usd: Decimal


class RevenueByModelResponse(BaseModel):
    items: list[RevenueByModelItem]
    total: int


class RevenueByMonitorResponse(BaseModel):
    items: list[RevenueByMonitorItem]
    total: int


class RevenueByPlatformItem(BaseModel):
    platform: str
    total_shifts: int
    total_tokens: int
    total_usd: Decimal


class RevenueByPlatformResponse(BaseModel):
    items: list[RevenueByPlatformItem]


class DailyRevenueItem(BaseModel):
    day: date
    total_shifts: int
    total_tokens: int
    total_usd: Decimal


class DailyRevenueResponse(BaseModel):
    items: list[DailyRevenueItem]


class ModelOverviewResponse(BaseModel):
    model_id: uuid.UUID
    period_from: date | None
    period_to: date | None
    total_shifts: int
    total_tokens: int
    total_usd: Decimal


class BestMonitorResponse(BaseModel):
    monitor_id: uuid.UUID
    full_name: str
    total_shifts: int
    total_usd: Decimal
