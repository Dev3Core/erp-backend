from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from redis.asyncio import Redis

from app.core.dependencies import CurrentUser
from app.redis import get_redis


def _client_ip(request: Request) -> str:
    fwd = request.headers.get("x-forwarded-for")
    if fwd:
        return fwd.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


async def _check(redis: Redis, key: str, limit: int, window_seconds: int) -> None:
    count = await redis.incr(key)
    if count == 1:
        await redis.expire(key, window_seconds)
    if count > limit:
        ttl = await redis.ttl(key)
        retry_after = max(ttl, 1)
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded",
            headers={"Retry-After": str(retry_after)},
        )


class RateLimitByIP:
    """Limit N hits per window per client IP. Scope disambiguates co-located limiters."""

    def __init__(self, scope: str, limit: int, window_seconds: int = 60):
        self.scope = scope
        self.limit = limit
        self.window_seconds = window_seconds

    async def __call__(
        self,
        request: Request,
        redis: Annotated[Redis, Depends(get_redis)],
    ) -> None:
        key = f"rl:ip:{self.scope}:{_client_ip(request)}"
        await _check(redis, key, self.limit, self.window_seconds)


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
        await _check(redis, key, self.limit, self.window_seconds)
