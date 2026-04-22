import uuid
from datetime import UTC, date, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import require_roles
from app.core.tenant import CurrentTenantId
from app.database import get_db
from app.models.user import Role
from app.schemas.monitor_salary import (
    CurrentSalaryResponse,
    MonitorSalaryCreate,
    MonitorSalaryListResponse,
    MonitorSalaryResponse,
)
from app.services.errors import ServiceError
from app.services.monitor_salary import MonitorSalaryService

router = APIRouter(prefix="/monitor-salaries", tags=["monitor-salaries"])

AdminOrOwner = require_roles(Role.OWNER, Role.ADMIN)


def _get_service(db: Annotated[AsyncSession, Depends(get_db)]) -> MonitorSalaryService:
    return MonitorSalaryService(db)


ServiceDep = Annotated[MonitorSalaryService, Depends(_get_service)]


@router.post(
    "",
    response_model=MonitorSalaryResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[AdminOrOwner],
)
async def create_salary(
    body: MonitorSalaryCreate,
    tenant_id: CurrentTenantId,
    svc: ServiceDep,
):
    try:
        return await svc.create(
            tenant_id=tenant_id,
            monitor_id=body.monitor_id,
            amount_cop=body.amount_cop,
            effective_from=body.effective_from,
            notes=body.notes,
        )
    except ServiceError as e:
        raise HTTPException(e.status_code, e.detail) from None


@router.get("", response_model=MonitorSalaryListResponse, dependencies=[AdminOrOwner])
async def list_salaries(
    tenant_id: CurrentTenantId,
    svc: ServiceDep,
    monitor_id: Annotated[uuid.UUID | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
):
    items, total = await svc.list(
        tenant_id=tenant_id,
        monitor_id=monitor_id,
        limit=limit,
        offset=offset,
    )
    return MonitorSalaryListResponse(
        items=[MonitorSalaryResponse.model_validate(x) for x in items], total=total
    )


@router.get(
    "/current/{monitor_id}",
    response_model=CurrentSalaryResponse,
    dependencies=[AdminOrOwner],
)
async def current_salary(
    monitor_id: uuid.UUID,
    tenant_id: CurrentTenantId,
    svc: ServiceDep,
    as_of: Annotated[date | None, Query()] = None,
):
    effective_date = as_of or datetime.now(UTC).date()
    entry = await svc.current_for(tenant_id=tenant_id, monitor_id=monitor_id, as_of=effective_date)
    if entry is None:
        raise HTTPException(404, "No salary history found for this monitor")
    return CurrentSalaryResponse(
        monitor_id=entry.monitor_id,
        amount_cop=entry.amount_cop,
        effective_from=entry.effective_from,
    )


@router.delete(
    "/{salary_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[AdminOrOwner],
)
async def delete_salary(
    salary_id: uuid.UUID,
    tenant_id: CurrentTenantId,
    svc: ServiceDep,
):
    try:
        await svc.delete(tenant_id=tenant_id, salary_id=salary_id)
    except ServiceError as e:
        raise HTTPException(e.status_code, e.detail) from None
    return None
