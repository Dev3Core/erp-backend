import uuid
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.exchange_rates import _get_service as _get_exchange_rate_service
from app.core.dependencies import require_roles
from app.core.tenant import CurrentTenantId
from app.database import get_db
from app.models.liquidation import LiquidationStatus
from app.models.user import Role
from app.schemas.liquidation import (
    LiquidationCreateFromShift,
    LiquidationListResponse,
    LiquidationResponse,
    LiquidationUpdate,
)
from app.services.errors import ServiceError
from app.services.exchange_rate import ExchangeRateService
from app.services.liquidation import LiquidationService

router = APIRouter(prefix="/liquidations", tags=["liquidations"])

AdminOrOwner = require_roles(Role.OWNER, Role.ADMIN)


def _get_service(
    db: Annotated[AsyncSession, Depends(get_db)],
    exchange_rates: Annotated[ExchangeRateService, Depends(_get_exchange_rate_service)],
) -> LiquidationService:
    return LiquidationService(db, exchange_rates)


ServiceDep = Annotated[LiquidationService, Depends(_get_service)]


@router.post(
    "/from-shift",
    response_model=LiquidationResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[AdminOrOwner],
)
async def create_from_shift(
    body: LiquidationCreateFromShift,
    tenant_id: CurrentTenantId,
    svc: ServiceDep,
):
    try:
        return await svc.create_from_shift(
            tenant_id=tenant_id,
            shift_id=body.shift_id,
            split_config_id=body.split_config_id,
            period_date=body.period_date,
            notes=body.notes,
        )
    except ServiceError as e:
        raise HTTPException(e.status_code, e.detail) from None


@router.get("", response_model=LiquidationListResponse, dependencies=[AdminOrOwner])
async def list_liquidations(
    tenant_id: CurrentTenantId,
    svc: ServiceDep,
    status: Annotated[LiquidationStatus | None, Query()] = None,
    date_from: Annotated[date | None, Query()] = None,
    date_to: Annotated[date | None, Query()] = None,
    shift_id: Annotated[uuid.UUID | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
):
    items, total = await svc.list(
        tenant_id=tenant_id,
        status=status,
        date_from=date_from,
        date_to=date_to,
        shift_id=shift_id,
        limit=limit,
        offset=offset,
    )
    return LiquidationListResponse(
        items=[LiquidationResponse.model_validate(x) for x in items], total=total
    )


@router.get(
    "/{liquidation_id}",
    response_model=LiquidationResponse,
    dependencies=[AdminOrOwner],
)
async def get_liquidation(
    liquidation_id: uuid.UUID,
    tenant_id: CurrentTenantId,
    svc: ServiceDep,
):
    try:
        return await svc.get(tenant_id=tenant_id, liquidation_id=liquidation_id)
    except ServiceError as e:
        raise HTTPException(e.status_code, e.detail) from None


@router.patch(
    "/{liquidation_id}",
    response_model=LiquidationResponse,
    dependencies=[AdminOrOwner],
)
async def update_liquidation(
    liquidation_id: uuid.UUID,
    body: LiquidationUpdate,
    tenant_id: CurrentTenantId,
    svc: ServiceDep,
):
    if body.status is None and body.notes is None:
        raise HTTPException(422, "At least one of status or notes must be provided")
    try:
        if body.status is not None:
            return await svc.transition_status(
                tenant_id=tenant_id,
                liquidation_id=liquidation_id,
                new_status=body.status,
                notes=body.notes,
            )
        liq = await svc.get(tenant_id=tenant_id, liquidation_id=liquidation_id)
        liq.notes = body.notes
        return liq
    except ServiceError as e:
        raise HTTPException(e.status_code, e.detail) from None


@router.delete(
    "/{liquidation_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[AdminOrOwner],
)
async def delete_liquidation(
    liquidation_id: uuid.UUID,
    tenant_id: CurrentTenantId,
    svc: ServiceDep,
):
    try:
        await svc.delete(tenant_id=tenant_id, liquidation_id=liquidation_id)
    except ServiceError as e:
        raise HTTPException(e.status_code, e.detail) from None
    return None
