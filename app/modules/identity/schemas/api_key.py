import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ApiKeyCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, max_length=255)
    ttl_hours: int = Field(default=24, ge=1, le=168)


class ApiKeyCreated(BaseModel):
    """Returned ONCE on creation. Includes the plaintext key; caller must store it."""

    id: uuid.UUID
    name: str | None
    plaintext_key: str
    prefix: str
    expires_at: datetime


class ApiKeyResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    name: str | None
    prefix: str
    expires_at: datetime
    last_used_at: datetime | None
    revoked_at: datetime | None
    created_at: datetime


class ApiKeyListResponse(BaseModel):
    items: list[ApiKeyResponse]
    total: int
