"""FastAPI dependencies owned by identity: JWT session user, role gates, tenant
scoping, API-key auth (Chrome extension) and per-user rate limiting.

They live here (not in `app.shared`) because they resolve the `User` ORM row
and verify API keys through `ApiKeyService`; `app.shared` must stay free of
domain models. Other modules get them through `app.modules.identity`.
"""

import uuid
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import APIKeyCookie, APIKeyHeader
from jose import JWTError
from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.identity.models.user import Role, User
from app.modules.identity.services.api_key import ApiKeyService
from app.shared.database import get_db
from app.shared.rate_limit import check_rate_limit
from app.shared.redis import get_redis
from app.shared.security import TokenType, decode_token, token_blacklist_key

_access_cookie_scheme = APIKeyCookie(name="access_token", auto_error=False)


async def _get_current_user(
    db: Annotated[AsyncSession, Depends(get_db)],
    redis: Annotated[Redis, Depends(get_redis)],
    access_token: Annotated[str | None, Depends(_access_cookie_scheme)] = None,
) -> User:
    if access_token is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Not authenticated")

    try:
        payload = decode_token(access_token)
    except JWTError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid token") from None

    if payload.get("type") != TokenType.ACCESS:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid token type")

    jti = str(payload.get("jti", ""))
    if jti and await redis.exists(token_blacklist_key(jti)):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Token revoked")

    stmt = select(User).where(User.id == uuid.UUID(str(payload["sub"])), User.is_active.is_(True))
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "User not found")

    user._token_payload = payload  # type: ignore[attr-defined]
    return user


CurrentUser = Annotated[User, Depends(_get_current_user)]


def require_roles(*roles: Role):
    allowed = set(roles)
    if Role.ADMIN in allowed:
        allowed.add(Role.OWNER)

    def dependency(user: CurrentUser) -> User:
        if user.role not in allowed:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Insufficient permissions")
        return user

    return Depends(dependency)


def require_mfa(user: CurrentUser) -> User:
    payload = getattr(user, "_token_payload", {})
    if user.mfa_enabled and not payload.get("mfa_verified", False):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "MFA verification required")
    return user


MFAVerifiedUser = Annotated[User, Depends(require_mfa)]


# --- Tenant scoping ---


async def _get_current_tenant_id(user: CurrentUser) -> uuid.UUID:
    return user.tenant_id


CurrentTenantId = Annotated[uuid.UUID, Depends(_get_current_tenant_id)]


# --- API-key auth (Chrome extension) ---
#
# Two accepted transports:
#   - HTTP header `X-API-Key: <plaintext>`
#   - OAuth2-style `Authorization: Bearer <plaintext>`
#
# The dep returns the owning `User`. Use `CurrentApiKeyUser` in routes exposed
# to the extension. Do NOT mix with `CurrentUser` (JWT) on the same endpoint.

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


# --- Per-user rate limiting ---


class RateLimitByUser:
    """Limit N hits per window per authenticated user."""

    def __init__(self, scope: str, limit: int, window_seconds: int = 60):
        self.scope = scope
        self.limit = limit
        self.window_seconds = window_seconds

    async def __call__(
        self,
        user: CurrentUser,
        redis: Annotated[Redis, Depends(get_redis)],
    ) -> None:
        key = f"rl:user:{self.scope}:{user.id}"
        await check_rate_limit(redis, key, self.limit, self.window_seconds)
