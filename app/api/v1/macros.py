import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import CurrentUser
from app.core.pagination import OffsetPage, OffsetParams, build_offset_page, offset_params
from app.core.tenant import CurrentTenantId
from app.database import get_db
from app.models.room import Platform
from app.schemas.macro import MacroCreate, MacroResponse, MacroUpdate
from app.services.errors import ServiceError
from app.services.macro import MacroService

router = APIRouter(prefix="/macros", tags=["macros"])


def _get_service(db: Annotated[AsyncSession, Depends(get_db)]) -> MacroService:
    return MacroService(db)


ServiceDep = Annotated[MacroService, Depends(_get_service)]


@router.post("", response_model=MacroResponse, status_code=status.HTTP_201_CREATED)
async def create_macro(
    body: MacroCreate,
    tenant_id: CurrentTenantId,
    user: CurrentUser,
    svc: ServiceDep,
):
    return await svc.create(
        tenant_id=tenant_id,
        user_id=user.id,
        label=body.label,
        content=body.content,
        platform=body.platform,
        position=body.position,
    )


@router.get("", response_model=OffsetPage[MacroResponse])
async def list_my_macros(
    tenant_id: CurrentTenantId,
    user: CurrentUser,
    svc: ServiceDep,
    params: Annotated[OffsetParams, Depends(offset_params)],
    platform: Annotated[Platform | None, Query()] = None,
    active_only: Annotated[bool, Query()] = True,
):
    items, total = await svc.list_for_user(
        tenant_id=tenant_id,
        user_id=user.id,
        params=params,
        platform=platform,
        active_only=active_only,
    )
    return build_offset_page([MacroResponse.model_validate(x) for x in items], total, params)


@router.patch("/{macro_id}", response_model=MacroResponse)
async def update_macro(
    macro_id: uuid.UUID,
    body: MacroUpdate,
    tenant_id: CurrentTenantId,
    user: CurrentUser,
    svc: ServiceDep,
):
    try:
        return await svc.update(
            tenant_id=tenant_id,
            user_id=user.id,
            macro_id=macro_id,
            label=body.label,
            content=body.content,
            platform=body.platform,
            position=body.position,
            is_active=body.is_active,
        )
    except ServiceError as e:
        raise HTTPException(e.status_code, e.detail) from None


@router.delete("/{macro_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_macro(
    macro_id: uuid.UUID,
    tenant_id: CurrentTenantId,
    user: CurrentUser,
    svc: ServiceDep,
):
    try:
        await svc.delete(tenant_id=tenant_id, user_id=user.id, macro_id=macro_id)
    except ServiceError as e:
        raise HTTPException(e.status_code, e.detail) from None
    return None
