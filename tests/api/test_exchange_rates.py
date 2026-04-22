from datetime import UTC, date, datetime
from decimal import Decimal

import pytest
from httpx import AsyncClient

from app.api.v1.exchange_rates import _get_service
from app.database import get_db
from app.main import app
from app.services.exchange_rate import ExchangeRateService


async def _fake_fetcher(target_date: date) -> Decimal:
    return Decimal("4123.45")


@pytest.fixture(autouse=True)
def _override_service():
    async def override(db=None):
        async for session in app.dependency_overrides[get_db]():
            return ExchangeRateService(session, fetcher=_fake_fetcher)

    app.dependency_overrides[_get_service] = override
    yield
    app.dependency_overrides.pop(_get_service, None)


class TestExchangeRates:
    async def test_get_today_fetches_and_caches(self, owner_client_a: AsyncClient):
        r1 = await owner_client_a.get("/api/v1/exchange-rates/today")
        assert r1.status_code == 200
        data = r1.json()
        assert Decimal(data["cop_per_usd"]) == Decimal("4123.45")
        assert data["rate_date"] == datetime.now(UTC).date().isoformat()

        # Second call hits the cache — still 200, same value.
        r2 = await owner_client_a.get("/api/v1/exchange-rates/today")
        assert r2.status_code == 200
        assert r2.json()["id"] == data["id"]

    async def test_manual_upsert_requires_admin(self, model_client_a: AsyncClient):
        resp = await model_client_a.post(
            "/api/v1/exchange-rates",
            json={"rate_date": "2026-04-22", "cop_per_usd": "4000.00", "source": "manual"},
        )
        assert resp.status_code == 403

    async def test_manual_upsert_happy_path(self, owner_client_a: AsyncClient):
        resp = await owner_client_a.post(
            "/api/v1/exchange-rates",
            json={"rate_date": "2026-04-22", "cop_per_usd": "4000.00", "source": "manual"},
        )
        assert resp.status_code == 201
        assert Decimal(resp.json()["cop_per_usd"]) == Decimal("4000.00")

    async def test_unauth_rejected(self, client: AsyncClient):
        assert (await client.get("/api/v1/exchange-rates/today")).status_code == 401
