"""Payroll: split configs, exchange rates (TRM), liquidations, monitor salaries
and salary advances.

Public API: `LiquidationService` + `get_exchange_rate_service` (used by the
insights exports), `ExchangeRateService` (type of that dependency) and
`Liquidation`/`LiquidationStatus` (read-only ORM access for insights).
"""

from app.modules.payroll.dependencies import get_exchange_rate_service
from app.modules.payroll.models.liquidation import Liquidation, LiquidationStatus
from app.modules.payroll.routers.exchange_rates import router as exchange_rates_router
from app.modules.payroll.routers.liquidations import router as liquidations_router
from app.modules.payroll.routers.monitor_salaries import router as monitor_salaries_router
from app.modules.payroll.routers.salary_advance_requests import router as salary_advance_router
from app.modules.payroll.routers.split_configs import router as split_configs_router
from app.modules.payroll.services.exchange_rate import ExchangeRateService
from app.modules.payroll.services.liquidation import LiquidationService

__all__ = [
    "ExchangeRateService",
    "Liquidation",
    "LiquidationService",
    "LiquidationStatus",
    "exchange_rates_router",
    "get_exchange_rate_service",
    "liquidations_router",
    "monitor_salaries_router",
    "salary_advance_router",
    "split_configs_router",
]
