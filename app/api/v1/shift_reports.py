import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import require_roles
from app.core.tenant import CurrentTenantId
from app.database import get_db
from app.models.user import Role
from app.schemas.shift_report import ShiftReportListResponse, ShiftReportResponse
from app.services.errors import ServiceError
from app.services.shift_report import ShiftReportService

router = APIRouter(prefix="/shift-reports", tags=["shift-reports"])

AnyAuthed = require_roles(Role.OWNER, Role.ADMIN, Role.MONITOR, Role.MODEL)


def _get_service(db: Annotated[AsyncSession, Depends(get_db)]) -> ShiftReportService:
    return ShiftReportService(db)


ServiceDep = Annotated[ShiftReportService, Depends(_get_service)]


@router.get("", response_model=ShiftReportListResponse, dependencies=[AnyAuthed])
async def list_reports(
    tenant_id: CurrentTenantId,
    svc: ServiceDep,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
):
    items, total = await svc.list_for_tenant(tenant_id=tenant_id, limit=limit, offset=offset)
    return ShiftReportListResponse(
        items=[ShiftReportResponse.model_validate(x) for x in items], total=total
    )


@router.get(
    "/by-shift/{shift_id}",
    response_model=ShiftReportResponse,
    dependencies=[AnyAuthed],
)
async def get_by_shift(
    shift_id: uuid.UUID,
    tenant_id: CurrentTenantId,
    svc: ServiceDep,
):
    try:
        return await svc.get_for_shift(tenant_id=tenant_id, shift_id=shift_id)
    except ServiceError as e:
        raise HTTPException(e.status_code, e.detail) from None
