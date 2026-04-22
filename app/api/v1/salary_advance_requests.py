import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import CurrentUser, require_roles
from app.core.tenant import CurrentTenantId
from app.database import get_db
from app.models.salary_advance_request import SalaryAdvanceStatus
from app.models.user import Role
from app.schemas.salary_advance_request import (
    SalaryAdvanceRequestCreate,
    SalaryAdvanceRequestListResponse,
    SalaryAdvanceRequestResponse,
    SalaryAdvanceRequestReview,
)
from app.services.errors import ServiceError
from app.services.salary_advance_request import SalaryAdvanceService

router = APIRouter(prefix="/salary-advances", tags=["salary-advances"])

AdminOrOwner = require_roles(Role.OWNER, Role.ADMIN)


def _get_service(db: Annotated[AsyncSession, Depends(get_db)]) -> SalaryAdvanceService:
    return SalaryAdvanceService(db)


ServiceDep = Annotated[SalaryAdvanceService, Depends(_get_service)]


@router.post(
    "",
    response_model=SalaryAdvanceRequestResponse,
    status_code=status.HTTP_201_CREATED,
)
async def request_advance(
    body: SalaryAdvanceRequestCreate,
    tenant_id: CurrentTenantId,
    user: CurrentUser,
    svc: ServiceDep,
):
    return await svc.request(
        tenant_id=tenant_id,
        requester=user,
        amount_cop=body.amount_cop,
        reason=body.reason,
    )


@router.get("/mine", response_model=SalaryAdvanceRequestListResponse)
async def list_mine(
    tenant_id: CurrentTenantId,
    user: CurrentUser,
    svc: ServiceDep,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
):
    items, total = await svc.list_mine(
        tenant_id=tenant_id, user_id=user.id, limit=limit, offset=offset
    )
    return SalaryAdvanceRequestListResponse(
        items=[SalaryAdvanceRequestResponse.model_validate(x) for x in items], total=total
    )


@router.get("", response_model=SalaryAdvanceRequestListResponse, dependencies=[AdminOrOwner])
async def list_all(
    tenant_id: CurrentTenantId,
    svc: ServiceDep,
    status: Annotated[SalaryAdvanceStatus | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
):
    items, total = await svc.list_for_admin(
        tenant_id=tenant_id, status=status, limit=limit, offset=offset
    )
    return SalaryAdvanceRequestListResponse(
        items=[SalaryAdvanceRequestResponse.model_validate(x) for x in items], total=total
    )


@router.get("/{request_id}", response_model=SalaryAdvanceRequestResponse)
async def get_request(
    request_id: uuid.UUID,
    tenant_id: CurrentTenantId,
    user: CurrentUser,
    svc: ServiceDep,
):
    try:
        return await svc.get(tenant_id=tenant_id, request_id=request_id, actor=user)
    except ServiceError as e:
        raise HTTPException(e.status_code, e.detail) from None


@router.patch(
    "/{request_id}/review",
    response_model=SalaryAdvanceRequestResponse,
    dependencies=[AdminOrOwner],
)
async def review_request(
    request_id: uuid.UUID,
    body: SalaryAdvanceRequestReview,
    tenant_id: CurrentTenantId,
    user: CurrentUser,
    svc: ServiceDep,
):
    try:
        return await svc.review(
            tenant_id=tenant_id,
            request_id=request_id,
            reviewer=user,
            new_status=body.status,
            review_notes=body.review_notes,
        )
    except ServiceError as e:
        raise HTTPException(e.status_code, e.detail) from None
