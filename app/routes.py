"""Composition root for the v1 API. Not a module: it may import every module's
public API. Include order is kept stable because it defines the OpenAPI order."""

from fastapi import APIRouter

from app.modules import (
    extension,
    health,
    identity,
    insights,
    notifications,
    payroll,
    shifts,
    studio,
)

v1_router = APIRouter()
v1_router.include_router(health.router, tags=["health"])
v1_router.include_router(identity.auth_router)
v1_router.include_router(identity.api_keys_router)
v1_router.include_router(identity.users_router)
v1_router.include_router(studio.rooms_router)
v1_router.include_router(studio.tags_router)
v1_router.include_router(payroll.split_configs_router)
v1_router.include_router(studio.technical_sheets_router)
v1_router.include_router(studio.bio_templates_router)
v1_router.include_router(shifts.shifts_router)
v1_router.include_router(shifts.shift_reports_router)
v1_router.include_router(studio.macros_router)
v1_router.include_router(payroll.exchange_rates_router)
v1_router.include_router(payroll.liquidations_router)
v1_router.include_router(payroll.monitor_salaries_router)
v1_router.include_router(insights.metrics_router)
v1_router.include_router(payroll.salary_advance_router)
v1_router.include_router(notifications.router)
v1_router.include_router(shifts.chat_router)
v1_router.include_router(insights.exports_router)
v1_router.include_router(extension.router)
