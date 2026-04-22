import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import require_roles
from app.core.tenant import CurrentTenantId
from app.database import get_db
from app.models.user import Role
from app.schemas.split_config import (
    SplitConfigCreate,
    SplitConfigListResponse,
    SplitConfigResponse,
    SplitConfigUpdate,
)
from app.services.errors import ServiceError
from app.services.split_config import SplitConfigService

router = APIRouter(prefix="/split-configs", tags=["split-configs"])

AdminOrOwner = require_roles(Role.OWNER, Role.ADMIN)


def _get_service(db: Annotated[AsyncSession, Depends(get_db)]) -> SplitConfigService:
    return SplitConfigService(db)


ServiceDep = Annotated[SplitConfigService, Depends(_get_service)]


@router.post(
    "",
    response_model=SplitConfigResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[AdminOrOwner],
)
async def create_split_config(
    body: SplitConfigCreate,
    tenant_id: CurrentTenantId,
    svc: ServiceDep,
):
    try:
        return await svc.create(
            tenant_id=tenant_id,
            label=body.label,
            platform_pct=body.platform_pct,
            studio_pct=body.studio_pct,
            model_pct=body.model_pct,
            is_default=body.is_default,
        )
    except ServiceError as e:
        raise HTTPException(e.status_code, e.detail) from None


@router.get("", response_model=SplitConfigListResponse, dependencies=[AdminOrOwner])
async def list_split_configs(
    tenant_id: CurrentTenantId,
    svc: ServiceDep,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
):
    items, total = await svc.list(tenant_id=tenant_id, limit=limit, offset=offset)
    return SplitConfigListResponse(
        items=[SplitConfigResponse.model_validate(c) for c in items], total=total
    )


@router.get(
    "/{config_id}",
    response_model=SplitConfigResponse,
    dependencies=[AdminOrOwner],
)
async def get_split_config(
    config_id: uuid.UUID,
    tenant_id: CurrentTenantId,
    svc: ServiceDep,
):
    try:
        return await svc.get(tenant_id=tenant_id, config_id=config_id)
    except ServiceError as e:
        raise HTTPException(e.status_code, e.detail) from None


@router.patch(
    "/{config_id}",
    response_model=SplitConfigResponse,
    dependencies=[AdminOrOwner],
)
async def update_split_config(
    config_id: uuid.UUID,
    body: SplitConfigUpdate,
    tenant_id: CurrentTenantId,
    svc: ServiceDep,
):
    try:
        return await svc.update(
            tenant_id=tenant_id,
            config_id=config_id,
            label=body.label,
            platform_pct=body.platform_pct,
            studio_pct=body.studio_pct,
            model_pct=body.model_pct,
            is_default=body.is_default,
        )
    except ServiceError as e:
        raise HTTPException(e.status_code, e.detail) from None


@router.delete(
    "/{config_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[AdminOrOwner],
)
async def delete_split_config(
    config_id: uuid.UUID,
    tenant_id: CurrentTenantId,
    svc: ServiceDep,
):
    try:
        await svc.delete(tenant_id=tenant_id, config_id=config_id)
    except ServiceError as e:
        raise HTTPException(e.status_code, e.detail) from None
    return None
