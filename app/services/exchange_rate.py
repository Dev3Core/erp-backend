import uuid
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Protocol
from urllib.parse import urlparse

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.exchange_rate import ExchangeRate
from app.services.errors import ServiceError

# Whitelisted upstream host (SSRF defense — prevents arbitrary URL fetches).
_ALLOWED_HOST = "www.datos.gov.co"
_DATASET_URL = "https://www.datos.gov.co/resource/32sa-8pi3.json"


class TrmFetcher(Protocol):
    async def __call__(self, target_date: date) -> Decimal: ...


class _RemoteUnavailableError(ServiceError):
    def __init__(self, detail: str = "Exchange rate source unavailable"):
        super().__init__(detail, status_code=503)


async def fetch_trm_from_datos_gov_co(target_date: date) -> Decimal:
    """Fetch the official TRM from the Colombian public dataset for a given date."""
    parsed = urlparse(_DATASET_URL)
    if parsed.hostname != _ALLOWED_HOST:
        raise _RemoteUnavailableError("Upstream host not allowed")

    # Dataset columns: valor (rate), vigenciadesde (valid from), vigenciahasta (valid to).
    iso = target_date.isoformat()
    params = {
        "$select": "valor,vigenciadesde,vigenciahasta",
        "$where": f"vigenciadesde <= '{iso}T00:00:00.000' "
        f"AND vigenciahasta >= '{iso}T00:00:00.000'",
        "$limit": "1",
    }

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(_DATASET_URL, params=params)
            resp.raise_for_status()
            rows = resp.json()
    except (httpx.HTTPError, ValueError) as exc:
        raise _RemoteUnavailableError() from exc

    if not rows:
        raise _RemoteUnavailableError(f"No TRM available for {iso}")
    try:
        return Decimal(str(rows[0]["valor"]))
    except (KeyError, ArithmeticError) as exc:
        raise _RemoteUnavailableError("Malformed TRM response") from exc


class ExchangeRateService:
    """Cache-aside for the official TRM. Reads from DB first, falls back to datos.gov.co."""

    def __init__(self, db: AsyncSession, fetcher: TrmFetcher = fetch_trm_from_datos_gov_co):
        self._db = db
        self._fetcher = fetcher

    async def get_for_date(self, target_date: date) -> ExchangeRate:
        cached = await self._get_cached(target_date)
        if cached is not None:
            return cached

        rate_value = await self._fetcher(target_date)
        return await self._store(
            target_date=target_date,
            cop_per_usd=rate_value,
            source="Banco de la Republica (datos.gov.co)",
        )

    async def get_today(self) -> ExchangeRate:
        return await self.get_for_date(datetime.now(UTC).date())

    async def upsert_manual(
        self, *, target_date: date, cop_per_usd: Decimal, source: str
    ) -> ExchangeRate:
        existing = await self._get_cached(target_date)
        if existing is not None:
            existing.cop_per_usd = cop_per_usd
            existing.source = source
            await self._db.flush()
            return existing
        return await self._store(
            target_date=target_date,
            cop_per_usd=cop_per_usd,
            source=source,
        )

    async def _get_cached(self, target_date: date) -> ExchangeRate | None:
        stmt = select(ExchangeRate).where(ExchangeRate.rate_date == target_date)
        return (await self._db.execute(stmt)).scalar_one_or_none()

    async def _store(
        self, *, target_date: date, cop_per_usd: Decimal, source: str
    ) -> ExchangeRate:
        rate = ExchangeRate(
            id=uuid.uuid4(),
            rate_date=target_date,
            cop_per_usd=cop_per_usd,
            source=source,
        )
        self._db.add(rate)
        await self._db.flush()
        return rate
