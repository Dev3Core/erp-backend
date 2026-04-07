import uuid
from typing import Annotated

from fastapi import Cookie, Depends, HTTPException, status
from jose import JWTError
from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import TokenType, decode_token, token_blacklist_key
from app.database import get_db
from app.models.user import Role, User
from app.redis import get_redis


async def _get_current_user(
    db: Annotated[AsyncSession, Depends(get_db)],
    redis: Annotated[Redis, Depends(get_redis)],
    access_token: Annotated[str | None, Cookie()] = None,
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
