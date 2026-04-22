from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.exchange_rates import _get_service as _get_exchange_rate_service
from app.core.dependencies import require_roles
from app.core.tenant import CurrentTenantId
from app.database import get_db
from app.models.liquidation import LiquidationStatus
from app.models.user import Role
from app.services.exchange_rate import ExchangeRateService
from app.services.exports import liquidations_to_csv, liquidations_to_pdf
from app.services.liquidation import LiquidationService

router = APIRouter(prefix="/exports", tags=["exports"])

AdminOrOwner = require_roles(Role.OWNER, Role.ADMIN)


def _get_liq_service(
    db: Annotated[AsyncSession, Depends(get_db)],
    fx: Annotated[ExchangeRateService, Depends(_get_exchange_rate_service)],
) -> LiquidationService:
    return LiquidationService(db, fx)


LiqDep = Annotated[LiquidationService, Depends(_get_liq_service)]


async def _fetch(
    svc: LiquidationService,
    tenant_id,
    status: LiquidationStatus | None,
    date_from: date | None,
    date_to: date | None,
):
    items, _ = await svc.list(
        tenant_id=tenant_id,
        status=status,
        date_from=date_from,
        date_to=date_to,
        limit=1000,
        offset=0,
    )
    return items


@router.get("/liquidations.csv", dependencies=[AdminOrOwner])
async def liquidations_csv(
    tenant_id: CurrentTenantId,
    svc: LiqDep,
    status: Annotated[LiquidationStatus | None, Query()] = None,
    date_from: Annotated[date | None, Query()] = None,
    date_to: Annotated[date | None, Query()] = None,
):
    rows = await _fetch(svc, tenant_id, status, date_from, date_to)
    payload = liquidations_to_csv(rows)
    return Response(
        content=payload,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=liquidations.csv"},
    )


@router.get("/liquidations.pdf", dependencies=[AdminOrOwner])
async def liquidations_pdf(
    tenant_id: CurrentTenantId,
    svc: LiqDep,
    db: Annotated[AsyncSession, Depends(get_db)],
    status: Annotated[LiquidationStatus | None, Query()] = None,
    date_from: Annotated[date | None, Query()] = None,
    date_to: Annotated[date | None, Query()] = None,
):
    from app.models.tenant import Tenant

    rows = await _fetch(svc, tenant_id, status, date_from, date_to)
    tenant = await db.get(Tenant, tenant_id)
    studio_name = tenant.name if tenant else "Studio"
    payload = liquidations_to_pdf(
        rows, studio_name=studio_name, period_from=date_from, period_to=date_to
    )
    return Response(
        content=payload,
        media_type="application/pdf",
        headers={"Content-Disposition": "attachment; filename=liquidations.pdf"},
    )
