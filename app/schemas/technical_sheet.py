import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class TechnicalSheetCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    model_id: uuid.UUID
    bio: str | None = Field(default=None, max_length=10000)
    languages: str | None = Field(default=None, max_length=500)
    categories: str | None = Field(default=None, max_length=500)
    notes: str | None = Field(default=None, max_length=5000)


class TechnicalSheetUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    bio: str | None = Field(default=None, max_length=10000)
    languages: str | None = Field(default=None, max_length=500)
    categories: str | None = Field(default=None, max_length=500)
    notes: str | None = Field(default=None, max_length=5000)


class TechnicalSheetResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    model_id: uuid.UUID
    bio: str | None
    languages: str | None
    categories: str | None
    notes: str | None
    created_at: datetime
    updated_at: datetime


class TechnicalSheetListResponse(BaseModel):
    items: list[TechnicalSheetResponse]
    total: int
