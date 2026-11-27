from fastapi import APIRouter

from app.modules.health.schemas import HealthCheck

router = APIRouter()


@router.get("/health", response_model=HealthCheck)
async def health_check() -> HealthCheck:
    return HealthCheck(status="ok", version="0.1.0")
