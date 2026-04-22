"""Authentication dependency for callers using an API key (Chrome extension).

Two accepted transports:
  - HTTP header `X-API-Key: <plaintext>`
  - OAuth2-style `Authorization: Bearer <plaintext>`

The dep returns the owning `User`. Use `CurrentApiKeyUser` in routes exposed
to the extension. Do NOT mix with `CurrentUser` (JWT) on the same endpoint.
"""

import uuid
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import APIKeyHeader
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.user import User
from app.services.api_key import ApiKeyService

_api_key_scheme = APIKeyHeader(name="X-API-Key", auto_error=False)


def _extract_bearer(request: Request) -> str | None:
    header = request.headers.get("authorization") or ""
    if header.lower().startswith("bearer "):
        return header.split(" ", 1)[1].strip()
    return None


async def _get_current_api_key_user(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    x_api_key: Annotated[str | None, Depends(_api_key_scheme)] = None,
) -> User:
    plaintext = x_api_key or _extract_bearer(request)
    if not plaintext:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "API key required")

    svc = ApiKeyService(db)
    entry = await svc.verify_plaintext(plaintext=plaintext)
    if entry is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid API key")

    stmt = select(User).where(
        User.id == uuid.UUID(str(entry.user_id)),
        User.is_active.is_(True),
        User.tenant_id == entry.tenant_id,
    )
    user = (await db.execute(stmt)).scalar_one_or_none()
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Associated user is inactive")
    return user


CurrentApiKeyUser = Annotated[User, Depends(_get_current_api_key_user)]
