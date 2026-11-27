import logging
from typing import ClassVar

from arq.connections import RedisSettings

from app.config import settings

logger = logging.getLogger(__name__)


async def placeholder_task(ctx: dict[str, object], message: str) -> str:
    logger.info("Executing placeholder task: %s", message)
    return f"Processed: {message}"


class WorkerSettings:
    functions: ClassVar[list] = [placeholder_task]
    redis_settings = RedisSettings.from_dsn(settings.REDIS_URL)
    max_jobs = 10
    job_timeout = 300
