from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import require_roles
from app.database import get_db
from app.models.user import Role
from app.schemas.exchange_rate import ExchangeRateCreate, ExchangeRateResponse
from app.services.errors import ServiceError
from app.services.exchange_rate import ExchangeRateService

router = APIRouter(prefix="/exchange-rates", tags=["exchange-rates"])

AdminOrOwner = require_roles(Role.OWNER, Role.ADMIN)
AnyAuthed = require_roles(Role.OWNER, Role.ADMIN, Role.MONITOR, Role.MODEL)


def _get_service(db: Annotated[AsyncSession, Depends(get_db)]) -> ExchangeRateService:
    return ExchangeRateService(db)


ServiceDep = Annotated[ExchangeRateService, Depends(_get_service)]


@router.get("/today", response_model=ExchangeRateResponse, dependencies=[AnyAuthed])
async def get_today_rate(svc: ServiceDep):
    try:
        return await svc.get_today()
    except ServiceError as e:
        raise HTTPException(e.status_code, e.detail) from None


@router.get(
    "/{rate_date}",
    response_model=ExchangeRateResponse,
    dependencies=[AnyAuthed],
)
async def get_rate_for_date(rate_date: date, svc: ServiceDep):
    try:
        return await svc.get_for_date(rate_date)
    except ServiceError as e:
        raise HTTPException(e.status_code, e.detail) from None


@router.post(
    "",
    response_model=ExchangeRateResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[AdminOrOwner],
)
async def upsert_rate_manual(body: ExchangeRateCreate, svc: ServiceDep):
    try:
        return await svc.upsert_manual(
            target_date=body.rate_date,
            cop_per_usd=body.cop_per_usd,
            source=body.source,
        )
    except ServiceError as e:
        raise HTTPException(e.status_code, e.detail) from None
