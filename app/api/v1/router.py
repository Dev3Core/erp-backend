from fastapi import APIRouter

from app.api.v1.api_keys import router as api_keys_router
from app.api.v1.auth import router as auth_router
from app.api.v1.bio_templates import router as bio_templates_router
from app.api.v1.chat import router as chat_router
from app.api.v1.exchange_rates import router as exchange_rates_router
from app.api.v1.exports import router as exports_router
from app.api.v1.extension import router as extension_router
from app.api.v1.health import router as health_router
from app.api.v1.liquidations import router as liquidations_router
from app.api.v1.macros import router as macros_router
from app.api.v1.metrics import router as metrics_router
from app.api.v1.monitor_salaries import router as monitor_salaries_router
from app.api.v1.notifications import router as notifications_router
from app.api.v1.rooms import router as rooms_router
from app.api.v1.salary_advance_requests import router as salary_advance_router
from app.api.v1.shift_reports import router as shift_reports_router
from app.api.v1.shifts import router as shifts_router
from app.api.v1.split_configs import router as split_configs_router
from app.api.v1.tags import router as tags_router
from app.api.v1.technical_sheets import router as technical_sheets_router
from app.api.v1.users import router as users_router

v1_router = APIRouter()
v1_router.include_router(health_router, tags=["health"])
v1_router.include_router(auth_router)
v1_router.include_router(api_keys_router)
v1_router.include_router(users_router)
v1_router.include_router(rooms_router)
v1_router.include_router(tags_router)
v1_router.include_router(split_configs_router)
v1_router.include_router(technical_sheets_router)
v1_router.include_router(bio_templates_router)
v1_router.include_router(shifts_router)
v1_router.include_router(shift_reports_router)
v1_router.include_router(macros_router)
v1_router.include_router(exchange_rates_router)
v1_router.include_router(liquidations_router)
v1_router.include_router(monitor_salaries_router)
v1_router.include_router(metrics_router)
v1_router.include_router(salary_advance_router)
v1_router.include_router(notifications_router)
v1_router.include_router(chat_router)
v1_router.include_router(exports_router)
v1_router.include_router(extension_router)
