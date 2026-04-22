import uuid
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import CurrentUser, require_roles
from app.core.tenant import CurrentTenantId
from app.database import get_db
from app.models.user import Role
from app.schemas.metrics import (
    BestMonitorResponse,
    DailyRevenueItem,
    DailyRevenueResponse,
    MetricsOverview,
    ModelOverviewResponse,
    RevenueByModelItem,
    RevenueByModelResponse,
    RevenueByMonitorItem,
    RevenueByMonitorResponse,
    RevenueByPlatformItem,
    RevenueByPlatformResponse,
)
from app.services.metrics import MetricsService

router = APIRouter(prefix="/metrics", tags=["metrics"])

AdminOrOwner = require_roles(Role.OWNER, Role.ADMIN)


def _get_service(db: Annotated[AsyncSession, Depends(get_db)]) -> MetricsService:
    return MetricsService(db)


ServiceDep = Annotated[MetricsService, Depends(_get_service)]


@router.get("/overview", response_model=MetricsOverview, dependencies=[AdminOrOwner])
async def overview(
    tenant_id: CurrentTenantId,
    svc: ServiceDep,
    date_from: Annotated[date | None, Query()] = None,
    date_to: Annotated[date | None, Query()] = None,
):
    data = await svc.overview(tenant_id=tenant_id, date_from=date_from, date_to=date_to)
    return MetricsOverview(**data)


@router.get(
    "/revenue-by-model",
    response_model=RevenueByModelResponse,
    dependencies=[AdminOrOwner],
)
async def revenue_by_model(
    tenant_id: CurrentTenantId,
    svc: ServiceDep,
    date_from: Annotated[date | None, Query()] = None,
    date_to: Annotated[date | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
):
    rows = await svc.revenue_by_model(
        tenant_id=tenant_id, date_from=date_from, date_to=date_to, limit=limit
    )
    items = [RevenueByModelItem(**r) for r in rows]
    return RevenueByModelResponse(items=items, total=len(items))


@router.get(
    "/revenue-by-monitor",
    response_model=RevenueByMonitorResponse,
    dependencies=[AdminOrOwner],
)
async def revenue_by_monitor(
    tenant_id: CurrentTenantId,
    svc: ServiceDep,
    date_from: Annotated[date | None, Query()] = None,
    date_to: Annotated[date | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
):
    rows = await svc.revenue_by_monitor(
        tenant_id=tenant_id, date_from=date_from, date_to=date_to, limit=limit
    )
    items = [RevenueByMonitorItem(**r) for r in rows]
    return RevenueByMonitorResponse(items=items, total=len(items))


@router.get(
    "/revenue-by-platform",
    response_model=RevenueByPlatformResponse,
    dependencies=[AdminOrOwner],
)
async def revenue_by_platform(
    tenant_id: CurrentTenantId,
    svc: ServiceDep,
    date_from: Annotated[date | None, Query()] = None,
    date_to: Annotated[date | None, Query()] = None,
):
    rows = await svc.revenue_by_platform(tenant_id=tenant_id, date_from=date_from, date_to=date_to)
    return RevenueByPlatformResponse(items=[RevenueByPlatformItem(**r) for r in rows])


@router.get(
    "/daily-revenue",
    response_model=DailyRevenueResponse,
    dependencies=[AdminOrOwner],
)
async def daily_revenue(
    tenant_id: CurrentTenantId,
    svc: ServiceDep,
    date_from: Annotated[date, Query()],
    date_to: Annotated[date, Query()],
    model_id: Annotated[uuid.UUID | None, Query()] = None,
):
    rows = await svc.daily_revenue(
        tenant_id=tenant_id,
        date_from=date_from,
        date_to=date_to,
        model_id=model_id,
    )
    return DailyRevenueResponse(items=[DailyRevenueItem(**r) for r in rows])


@router.get("/model/overview", response_model=ModelOverviewResponse)
async def my_model_overview(
    tenant_id: CurrentTenantId,
    user: CurrentUser,
    svc: ServiceDep,
    date_from: Annotated[date | None, Query()] = None,
    date_to: Annotated[date | None, Query()] = None,
):
    if user.role != Role.MODEL:
        raise HTTPException(403, "Endpoint only available to MODEL role")
    data = await svc.model_overview(
        tenant_id=tenant_id,
        model_id=user.id,
        date_from=date_from,
        date_to=date_to,
    )
    return ModelOverviewResponse(**data)


@router.get("/model/best-monitor", response_model=BestMonitorResponse | None)
async def my_best_monitor(
    tenant_id: CurrentTenantId,
    user: CurrentUser,
    svc: ServiceDep,
):
    if user.role != Role.MODEL:
        raise HTTPException(403, "Endpoint only available to MODEL role")
    row = await svc.best_monitor_for_model(tenant_id=tenant_id, model_id=user.id)
    if row is None:
        return None
    return BestMonitorResponse(**row)
