from collections.abc import AsyncGenerator

from redis.asyncio import ConnectionPool, Redis

from app.config import settings

pool: ConnectionPool | None = None


async def init_redis() -> None:
    global pool
    pool = ConnectionPool.from_url(settings.REDIS_URL, decode_responses=True)


async def close_redis() -> None:
    global pool
    if pool is not None:
        await pool.aclose()
        pool = None


async def get_redis() -> AsyncGenerator[Redis, None]:
    if pool is None:
        raise RuntimeError("Redis connection pool is not initialized")
    client = Redis(connection_pool=pool)
    try:
        yield client
    finally:
        await client.aclose()
