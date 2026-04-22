import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import require_roles
from app.core.tenant import CurrentTenantId
from app.database import get_db
from app.models.user import Role
from app.schemas.technical_sheet import (
    TechnicalSheetCreate,
    TechnicalSheetListResponse,
    TechnicalSheetResponse,
    TechnicalSheetUpdate,
)
from app.services.errors import ServiceError
from app.services.technical_sheet import TechnicalSheetService

router = APIRouter(prefix="/technical-sheets", tags=["technical-sheets"])

AdminOrOwnerOrMonitor = require_roles(Role.OWNER, Role.ADMIN, Role.MONITOR)
AnyAuthed = require_roles(Role.OWNER, Role.ADMIN, Role.MONITOR, Role.MODEL)


def _get_service(db: Annotated[AsyncSession, Depends(get_db)]) -> TechnicalSheetService:
    return TechnicalSheetService(db)


ServiceDep = Annotated[TechnicalSheetService, Depends(_get_service)]


@router.post(
    "",
    response_model=TechnicalSheetResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[AdminOrOwnerOrMonitor],
)
async def create_sheet(
    body: TechnicalSheetCreate,
    tenant_id: CurrentTenantId,
    svc: ServiceDep,
):
    try:
        return await svc.create(
            tenant_id=tenant_id,
            model_id=body.model_id,
            bio=body.bio,
            languages=body.languages,
            categories=body.categories,
            notes=body.notes,
        )
    except ServiceError as e:
        raise HTTPException(e.status_code, e.detail) from None


@router.get("", response_model=TechnicalSheetListResponse, dependencies=[AnyAuthed])
async def list_sheets(
    tenant_id: CurrentTenantId,
    svc: ServiceDep,
    model_id: Annotated[uuid.UUID | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
):
    items, total = await svc.list(
        tenant_id=tenant_id,
        model_id=model_id,
        limit=limit,
        offset=offset,
    )
    return TechnicalSheetListResponse(
        items=[TechnicalSheetResponse.model_validate(s) for s in items], total=total
    )


@router.get(
    "/{sheet_id}",
    response_model=TechnicalSheetResponse,
    dependencies=[AnyAuthed],
)
async def get_sheet(sheet_id: uuid.UUID, tenant_id: CurrentTenantId, svc: ServiceDep):
    try:
        return await svc.get(tenant_id=tenant_id, sheet_id=sheet_id)
    except ServiceError as e:
        raise HTTPException(e.status_code, e.detail) from None


@router.patch(
    "/{sheet_id}",
    response_model=TechnicalSheetResponse,
    dependencies=[AdminOrOwnerOrMonitor],
)
async def update_sheet(
    sheet_id: uuid.UUID,
    body: TechnicalSheetUpdate,
    tenant_id: CurrentTenantId,
    svc: ServiceDep,
):
    try:
        return await svc.update(
            tenant_id=tenant_id,
            sheet_id=sheet_id,
            bio=body.bio,
            languages=body.languages,
            categories=body.categories,
            notes=body.notes,
        )
    except ServiceError as e:
        raise HTTPException(e.status_code, e.detail) from None


@router.delete(
    "/{sheet_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[AdminOrOwnerOrMonitor],
)
async def delete_sheet(sheet_id: uuid.UUID, tenant_id: CurrentTenantId, svc: ServiceDep):
    try:
        await svc.delete(tenant_id=tenant_id, sheet_id=sheet_id)
    except ServiceError as e:
        raise HTTPException(e.status_code, e.detail) from None
    return None
