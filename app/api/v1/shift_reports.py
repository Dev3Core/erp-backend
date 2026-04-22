import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import require_roles
from app.core.pagination import CursorPage, CursorParams, build_cursor_page, cursor_params
from app.core.tenant import CurrentTenantId
from app.database import get_db
from app.models.user import Role
from app.schemas.shift_report import ShiftReportResponse
from app.services.errors import ServiceError
from app.services.shift_report import ShiftReportService

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
