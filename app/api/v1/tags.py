import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import require_roles
from app.core.pagination import OffsetPage, OffsetParams, build_offset_page, offset_params
from app.core.tenant import CurrentTenantId
from app.database import get_db
from app.models.room import Platform
from app.models.user import Role
from app.schemas.tag import TagCreate, TagResponse, TagUpdate
from app.services.errors import ServiceError
from app.services.tag import TagService

router = APIRouter(prefix="/tags", tags=["tags"])

MonitorUp = require_roles(Role.OWNER, Role.ADMIN, Role.MONITOR)
AnyAuthed = require_roles(Role.OWNER, Role.ADMIN, Role.MONITOR, Role.MODEL)


def _get_service(db: Annotated[AsyncSession, Depends(get_db)]) -> TagService:
    return TagService(db)


ServiceDep = Annotated[TagService, Depends(_get_service)]


@router.post(
    "",
    response_model=TagResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[MonitorUp],
)
async def create_tag(
    body: TagCreate,
    tenant_id: CurrentTenantId,
    svc: ServiceDep,
):
    try:
        return await svc.create(
            tenant_id=tenant_id,
            room_id=body.room_id,
            value=body.value,
            platform=body.platform,
        )
    except ServiceError as e:
        raise HTTPException(e.status_code, e.detail) from None


@router.get("", response_model=OffsetPage[TagResponse], dependencies=[AnyAuthed])
async def list_tags(
    tenant_id: CurrentTenantId,
    svc: ServiceDep,
    params: Annotated[OffsetParams, Depends(offset_params)],
    room_id: Annotated[uuid.UUID | None, Query()] = None,
    platform: Annotated[Platform | None, Query()] = None,
    active_only: Annotated[bool, Query()] = False,
):
    items, total = await svc.list_for_room(
        tenant_id=tenant_id,
        params=params,
        room_id=room_id,
        platform=platform,
        active_only=active_only,
    )
    return build_offset_page([TagResponse.model_validate(x) for x in items], total, params)


@router.patch("/{tag_id}", response_model=TagResponse, dependencies=[MonitorUp])
async def update_tag(
    tag_id: uuid.UUID,
    body: TagUpdate,
    tenant_id: CurrentTenantId,
    svc: ServiceDep,
):
    if body.is_active is None:
        raise HTTPException(422, "No changes provided")
    try:
        return await svc.set_active(tenant_id=tenant_id, tag_id=tag_id, is_active=body.is_active)
    except ServiceError as e:
        raise HTTPException(e.status_code, e.detail) from None


@router.delete("/{tag_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=[MonitorUp])
async def delete_tag(
    tag_id: uuid.UUID,
    tenant_id: CurrentTenantId,
    svc: ServiceDep,
):
    try:
        await svc.delete(tenant_id=tenant_id, tag_id=tag_id)
    except ServiceError as e:
        raise HTTPException(e.status_code, e.detail) from None
    return None
