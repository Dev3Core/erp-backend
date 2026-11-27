"""FastAPI dependencies shared by payroll routers and exposed to other modules.

`get_exchange_rate_service` is the single override point for the TRM provider
(tests replace it via `app.dependency_overrides`), so every router that needs
exchange rates must depend on this exact callable.
"""

from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.payroll.services.exchange_rate import ExchangeRateService
from app.shared.database import get_db


def get_exchange_rate_service(db: Annotated[AsyncSession, Depends(get_db)]) -> ExchangeRateService:
    return ExchangeRateService(db)
