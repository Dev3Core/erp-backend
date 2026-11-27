import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, model_validator


def _round(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"))


class SplitConfigCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    label: str = Field(min_length=1, max_length=255)
    platform_pct: Decimal = Field(ge=0, le=100, decimal_places=2)
    studio_pct: Decimal = Field(ge=0, le=100, decimal_places=2)
    model_pct: Decimal = Field(ge=0, le=100, decimal_places=2)
    is_default: bool = False

    @model_validator(mode="after")
    def _pcts_sum_to_100(self) -> "SplitConfigCreate":
        total = _round(self.platform_pct) + _round(self.studio_pct) + _round(self.model_pct)
        if _round(total) != Decimal("100.00"):
            raise ValueError("platform_pct + studio_pct + model_pct must equal 100")
        return self


class SplitConfigUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    label: str | None = Field(default=None, min_length=1, max_length=255)
    platform_pct: Decimal | None = Field(default=None, ge=0, le=100, decimal_places=2)
    studio_pct: Decimal | None = Field(default=None, ge=0, le=100, decimal_places=2)
    model_pct: Decimal | None = Field(default=None, ge=0, le=100, decimal_places=2)
    is_default: bool | None = None

    @model_validator(mode="after")
    def _pcts_coherent(self) -> "SplitConfigUpdate":
        pcts = [self.platform_pct, self.studio_pct, self.model_pct]
        provided = [p for p in pcts if p is not None]
        if 0 < len(provided) < 3:
            raise ValueError("Provide all three percentages together or none")
        if len(provided) == 3:
            total = sum(_round(p) for p in provided)
            if _round(total) != Decimal("100.00"):
                raise ValueError("platform_pct + studio_pct + model_pct must equal 100")
        return self


class SplitConfigResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    label: str
    platform_pct: Decimal
    studio_pct: Decimal
    model_pct: Decimal
    is_default: bool
    created_at: datetime


class SplitConfigListResponse(BaseModel):
    items: list[SplitConfigResponse]
    total: int
