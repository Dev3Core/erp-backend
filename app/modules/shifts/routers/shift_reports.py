import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.identity import CurrentTenantId, Role, require_roles
from app.modules.shifts.schemas.shift_report import ShiftReportResponse
from app.modules.shifts.services.shift_report import ShiftReportService
from app.shared.database import get_db
from app.shared.errors import ServiceError
from app.shared.pagination import CursorPage, CursorParams, build_cursor_page, cursor_params

router = APIRouter(prefix="/shift-reports", tags=["shift-reports"])

AnyAuthed = require_roles(Role.OWNER, Role.ADMIN, Role.MONITOR, Role.MODEL)


def _get_service(db: Annotated[AsyncSession, Depends(get_db)]) -> ShiftReportService:
    return ShiftReportService(db)


ServiceDep = Annotated[ShiftReportService, Depends(_get_service)]


@router.get("", response_model=CursorPage[ShiftReportResponse], dependencies=[AnyAuthed])
async def list_reports(
    tenant_id: CurrentTenantId,
    svc: ServiceDep,
    params: Annotated[CursorParams, Depends(cursor_params)],
):
    items, next_cursor, prev_cursor = await svc.list_for_tenant(tenant_id=tenant_id, params=params)
    return build_cursor_page(
        [ShiftReportResponse.model_validate(x) for x in items],
        next_cursor,
        prev_cursor,
        params.limit,
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
