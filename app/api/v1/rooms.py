import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import require_roles
from app.core.tenant import CurrentTenantId
from app.database import get_db
from app.models.room import Platform, RoomStatus
from app.models.user import Role
from app.schemas.room import RoomCreate, RoomListResponse, RoomResponse, RoomUpdate
from app.services.errors import ServiceError
from app.services.room import RoomService

router = APIRouter(prefix="/rooms", tags=["rooms"])

AdminOrOwner = require_roles(Role.OWNER, Role.ADMIN)
AnyAuthed = require_roles(Role.OWNER, Role.ADMIN, Role.MONITOR, Role.MODEL)


def _get_service(db: Annotated[AsyncSession, Depends(get_db)]) -> RoomService:
    return RoomService(db)


RoomServiceDep = Annotated[RoomService, Depends(_get_service)]


@router.post(
    "",
    response_model=RoomResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[AdminOrOwner],
)
async def create_room(body: RoomCreate, tenant_id: CurrentTenantId, svc: RoomServiceDep):
    try:
        return await svc.create(
            tenant_id=tenant_id,
            name=body.name,
            platform=body.platform,
            url=str(body.url),
        )
    except ServiceError as e:
        raise HTTPException(e.status_code, e.detail) from None


@router.get("", response_model=RoomListResponse, dependencies=[AnyAuthed])
async def list_rooms(
    tenant_id: CurrentTenantId,
    svc: RoomServiceDep,
    platform: Annotated[Platform | None, Query()] = None,
    status: Annotated[RoomStatus | None, Query()] = None,
    is_active: Annotated[bool | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
):
    items, total = await svc.list(
        tenant_id=tenant_id,
        platform=platform,
        status=status,
        is_active=is_active,
        limit=limit,
        offset=offset,
    )
    return RoomListResponse(items=[RoomResponse.model_validate(r) for r in items], total=total)


@router.get("/{room_id}", response_model=RoomResponse, dependencies=[AnyAuthed])
async def get_room(room_id: uuid.UUID, tenant_id: CurrentTenantId, svc: RoomServiceDep):
    try:
        return await svc.get(tenant_id=tenant_id, room_id=room_id)
    except ServiceError as e:
        raise HTTPException(e.status_code, e.detail) from None


@router.patch("/{room_id}", response_model=RoomResponse, dependencies=[AdminOrOwner])
async def update_room(
    room_id: uuid.UUID,
    body: RoomUpdate,
    tenant_id: CurrentTenantId,
    svc: RoomServiceDep,
):
    try:
        return await svc.update(
            tenant_id=tenant_id,
            room_id=room_id,
            name=body.name,
            url=str(body.url) if body.url else None,
            status=body.status,
            is_active=body.is_active,
        )
    except ServiceError as e:
        raise HTTPException(e.status_code, e.detail) from None


@router.delete(
    "/{room_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[AdminOrOwner],
)
async def deactivate_room(room_id: uuid.UUID, tenant_id: CurrentTenantId, svc: RoomServiceDep):
    try:
        await svc.deactivate(tenant_id=tenant_id, room_id=room_id)
    except ServiceError as e:
        raise HTTPException(e.status_code, e.detail) from None
    return None
