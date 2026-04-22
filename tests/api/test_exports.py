from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

import pytest
from httpx import AsyncClient

from app.api.v1.exchange_rates import _get_service as _get_fx_service
from app.database import get_db
from app.main import app
from app.services.exchange_rate import ExchangeRateService


async def _fake_trm(target_date: date) -> Decimal:
    return Decimal("4000.00")


@pytest.fixture(autouse=True)
def _override_fx():
    async def override(db=None):
        async for session in app.dependency_overrides[get_db]():
            return ExchangeRateService(session, fetcher=_fake_trm)

    app.dependency_overrides[_get_fx_service] = override
    yield
    app.dependency_overrides.pop(_get_fx_service, None)


async def _seed_liquidation(client: AsyncClient) -> None:
    mid = (
        await client.post(
            "/api/v1/users",
            json={
                "email": "exp_model@a.com",
                "password": "StrongPass123",
                "full_name": "Exp Model",
                "role": "MODEL",
            },
        )
    ).json()["id"]
    rid = (
        await client.post(
            "/api/v1/rooms",
            json={
                "name": "Exp Room",
                "platform": "CHATURBATE",
                "url": "https://chaturbate.com/exp/",
            },
        )
    ).json()["id"]
    base = datetime.now(UTC).replace(microsecond=0)
    sh = await client.post(
        "/api/v1/shifts",
        json={
            "model_id": mid,
            "room_id": rid,
            "start_time": base.isoformat(),
            "end_time": (base + timedelta(hours=2)).isoformat(),
        },
    )
    sid = sh.json()["id"]
    await client.patch(
        f"/api/v1/shifts/{sid}",
        json={"status": "FINISHED", "tokens_earned": 2000, "usd_earned": "100.00"},
    )
    await client.post(
        "/api/v1/split-configs",
        json={
            "label": "Default",
            "platform_pct": "50.00",
            "studio_pct": "30.00",
            "model_pct": "20.00",
            "is_default": True,
        },
    )
    r = await client.post("/api/v1/liquidations/from-shift", json={"shift_id": sid})
    assert r.status_code == 201


class TestExports:
    async def test_csv_export(self, owner_client_a: AsyncClient):
        await _seed_liquidation(owner_client_a)
        resp = await owner_client_a.get("/api/v1/exports/liquidations.csv")
        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("text/csv")
        text = resp.text
        assert "shift_id" in text
        assert "4000.00" in text or "4000" in text

    async def test_pdf_export(self, owner_client_a: AsyncClient):
        await _seed_liquidation(owner_client_a)
        resp = await owner_client_a.get("/api/v1/exports/liquidations.pdf")
        assert resp.status_code == 200
        assert resp.headers["content-type"] == "application/pdf"
        # PDF magic bytes
        assert resp.content.startswith(b"%PDF-")

    async def test_model_cannot_export(self, model_client_a: AsyncClient):
        resp = await model_client_a.get("/api/v1/exports/liquidations.csv")
        assert resp.status_code == 403
