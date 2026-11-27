import uuid
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.identity import CurrentTenantId, Role, require_roles
from app.modules.shifts.models.shift import ShiftStatus
from app.modules.shifts.schemas.shift import ShiftCreate, ShiftResponse, ShiftUpdate
from app.modules.shifts.services.shift import ShiftService
from app.shared.database import get_db
from app.shared.errors import ServiceError
from app.shared.pagination import CursorPage, CursorParams, build_cursor_page, cursor_params

router = APIRouter(prefix="/shifts", tags=["shifts"])

AdminOrOwnerOrMonitor = require_roles(Role.OWNER, Role.ADMIN, Role.MONITOR)
AnyAuthed = require_roles(Role.OWNER, Role.ADMIN, Role.MONITOR, Role.MODEL)


def _get_service(db: Annotated[AsyncSession, Depends(get_db)]) -> ShiftService:
    return ShiftService(db)


ServiceDep = Annotated[ShiftService, Depends(_get_service)]


@router.post(
    "",
    response_model=ShiftResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[AdminOrOwnerOrMonitor],
)
async def create_shift(
    body: ShiftCreate,
    tenant_id: CurrentTenantId,
    svc: ServiceDep,
):
    try:
        return await svc.create(
            tenant_id=tenant_id,
            model_id=body.model_id,
            room_id=body.room_id,
            monitor_id=body.monitor_id,
            start_time=body.start_time,
            end_time=body.end_time,
        )
    except ServiceError as e:
        raise HTTPException(e.status_code, e.detail) from None


@router.get("", response_model=CursorPage[ShiftResponse], dependencies=[AnyAuthed])
async def list_shifts(
    tenant_id: CurrentTenantId,
    svc: ServiceDep,
    params: Annotated[CursorParams, Depends(cursor_params)],
    model_id: Annotated[uuid.UUID | None, Query()] = None,
    room_id: Annotated[uuid.UUID | None, Query()] = None,
    monitor_id: Annotated[uuid.UUID | None, Query()] = None,
    status: Annotated[ShiftStatus | None, Query()] = None,
    date_from: Annotated[datetime | None, Query()] = None,
    date_to: Annotated[datetime | None, Query()] = None,
):
    items, next_cursor, prev_cursor = await svc.list(
        tenant_id=tenant_id,
        params=params,
        model_id=model_id,
        room_id=room_id,
        monitor_id=monitor_id,
        status=status,
        date_from=date_from,
        date_to=date_to,
    )
    return build_cursor_page(
        [ShiftResponse.model_validate(s) for s in items],
        next_cursor,
        prev_cursor,
        params.limit,
    )


@router.get("/{shift_id}", response_model=ShiftResponse, dependencies=[AnyAuthed])
async def get_shift(shift_id: uuid.UUID, tenant_id: CurrentTenantId, svc: ServiceDep):
    try:
        return await svc.get(tenant_id=tenant_id, shift_id=shift_id)
    except ServiceError as e:
        raise HTTPException(e.status_code, e.detail) from None


@router.patch(
    "/{shift_id}",
    response_model=ShiftResponse,
    dependencies=[AdminOrOwnerOrMonitor],
)
async def update_shift(
    shift_id: uuid.UUID,
    body: ShiftUpdate,
    tenant_id: CurrentTenantId,
    svc: ServiceDep,
):
    try:
        return await svc.update(
            tenant_id=tenant_id,
            shift_id=shift_id,
            monitor_id=body.monitor_id,
            status=body.status,
            start_time=body.start_time,
            end_time=body.end_time,
            tokens_earned=body.tokens_earned,
            usd_earned=body.usd_earned,
        )
    except ServiceError as e:
        raise HTTPException(e.status_code, e.detail) from None


@router.delete(
    "/{shift_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[AdminOrOwnerOrMonitor],
)
async def delete_shift(shift_id: uuid.UUID, tenant_id: CurrentTenantId, svc: ServiceDep):
    try:
        await svc.delete(tenant_id=tenant_id, shift_id=shift_id)
    except ServiceError as e:
        raise HTTPException(e.status_code, e.detail) from None
    return None
