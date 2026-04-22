from fastapi import APIRouter

from app.api.v1.auth import router as auth_router
from app.api.v1.exchange_rates import router as exchange_rates_router
from app.api.v1.health import router as health_router
from app.api.v1.rooms import router as rooms_router
from app.api.v1.shifts import router as shifts_router
from app.api.v1.split_configs import router as split_configs_router
from app.api.v1.technical_sheets import router as technical_sheets_router
from app.api.v1.users import router as users_router

v1_router = APIRouter()
v1_router.include_router(health_router, tags=["health"])
v1_router.include_router(auth_router)
v1_router.include_router(users_router)
v1_router.include_router(rooms_router)
v1_router.include_router(split_configs_router)
v1_router.include_router(technical_sheets_router)
v1_router.include_router(shifts_router)
v1_router.include_router(exchange_rates_router)
