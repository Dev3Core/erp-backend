import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class BioTemplateCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=120)
    html_content: str = Field(min_length=1, max_length=20000)


class BioTemplateUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=1, max_length=120)
    html_content: str | None = Field(default=None, min_length=1, max_length=20000)
    is_active: bool | None = None


class BioTemplateResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    created_by: uuid.UUID | None
    name: str
    html_content: str
    is_active: bool
    created_at: datetime


class BioTemplateListResponse(BaseModel):
    items: list[BioTemplateResponse]
    total: int


class BioSanitizeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    html_content: str = Field(min_length=1, max_length=20000)


class BioSanitizeResponse(BaseModel):
    original_length: int
    sanitized_length: int
    html_content: str
