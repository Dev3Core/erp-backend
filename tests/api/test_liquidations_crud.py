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


ROOM_PAYLOAD = {
    "name": "Room L",
    "platform": "CHATURBATE",
    "url": "https://chaturbate.com/liq/",
}


async def _seed_finished_shift(client: AsyncClient) -> dict:
    mr = await client.post(
        "/api/v1/users",
        json={
            "email": "liq_model@a.com",
            "password": "StrongPass123",
            "full_name": "Liq Model",
            "role": "MODEL",
        },
    )
    model_id = mr.json()["id"]
    rr = await client.post("/api/v1/rooms", json=ROOM_PAYLOAD)
    room_id = rr.json()["id"]

    start = datetime.now(UTC).replace(microsecond=0)
    sh = await client.post(
        "/api/v1/shifts",
        json={
            "model_id": model_id,
            "room_id": room_id,
            "start_time": start.isoformat(),
            "end_time": (start + timedelta(hours=3)).isoformat(),
        },
    )
    shift_id = sh.json()["id"]
    await client.patch(
        f"/api/v1/shifts/{shift_id}",
        json={"status": "FINISHED", "tokens_earned": 2000, "usd_earned": "100.00"},
    )

    # Default split: 50/30/20 (platform/studio/model)
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
    return {"model_id": model_id, "room_id": room_id, "shift_id": shift_id}


class TestLiquidationsCrud:
    async def test_create_from_shift_with_default_split(self, owner_client_a: AsyncClient):
        ctx = await _seed_finished_shift(owner_client_a)
        resp = await owner_client_a.post(
            "/api/v1/liquidations/from-shift",
            json={"shift_id": ctx["shift_id"]},
        )
        assert resp.status_code == 201, resp.text
        data = resp.json()
        # 100 USD gross -> -50% platform = 50 post-platform;
        # model gets 20/(30+20) = 40% of post-platform -> 20 USD net
        # 20 USD * 4000 COP/USD = 80000 COP
        assert Decimal(data["gross_usd"]) == Decimal("100.00")
        assert Decimal(data["net_usd"]) == Decimal("20.00")
        assert Decimal(data["cop_amount"]) == Decimal("80000.00")
        assert Decimal(data["trm_used"]) == Decimal("4000.00")
        assert data["status"] == "PENDING"

    async def test_duplicate_rejected(self, owner_client_a: AsyncClient):
        ctx = await _seed_finished_shift(owner_client_a)
        r1 = await owner_client_a.post(
            "/api/v1/liquidations/from-shift", json={"shift_id": ctx["shift_id"]}
        )
        assert r1.status_code == 201
        r2 = await owner_client_a.post(
            "/api/v1/liquidations/from-shift", json={"shift_id": ctx["shift_id"]}
        )
        assert r2.status_code == 409

    async def test_unfinished_shift_rejected(self, owner_client_a: AsyncClient):
        ctx = await _seed_finished_shift(owner_client_a)
        # Reset the shift back to SCHEDULED
        await owner_client_a.patch(
            f"/api/v1/shifts/{ctx['shift_id']}", json={"status": "SCHEDULED"}
        )
        resp = await owner_client_a.post(
            "/api/v1/liquidations/from-shift", json={"shift_id": ctx["shift_id"]}
        )
        assert resp.status_code == 422

    async def test_status_transitions(self, owner_client_a: AsyncClient):
        ctx = await _seed_finished_shift(owner_client_a)
        created = await owner_client_a.post(
            "/api/v1/liquidations/from-shift", json={"shift_id": ctx["shift_id"]}
        )
        liq_id = created.json()["id"]

        r = await owner_client_a.patch(
            f"/api/v1/liquidations/{liq_id}", json={"status": "APPROVED"}
        )
        assert r.status_code == 200 and r.json()["status"] == "APPROVED"

        r = await owner_client_a.patch(f"/api/v1/liquidations/{liq_id}", json={"status": "PAID"})
        assert r.status_code == 200 and r.json()["status"] == "PAID"

    async def test_invalid_transition_rejected(self, owner_client_a: AsyncClient):
        ctx = await _seed_finished_shift(owner_client_a)
        created = await owner_client_a.post(
            "/api/v1/liquidations/from-shift", json={"shift_id": ctx["shift_id"]}
        )
        liq_id = created.json()["id"]
        # PENDING -> PAID directly is not allowed
        resp = await owner_client_a.patch(
            f"/api/v1/liquidations/{liq_id}", json={"status": "PAID"}
        )
        assert resp.status_code == 422

    async def test_model_cannot_access(
        self, owner_client_a: AsyncClient, model_client_a: AsyncClient
    ):
        ctx = await _seed_finished_shift(owner_client_a)
        await owner_client_a.post(
            "/api/v1/liquidations/from-shift", json={"shift_id": ctx["shift_id"]}
        )
        resp = await model_client_a.get("/api/v1/liquidations")
        assert resp.status_code == 403

    async def test_tenant_isolation(
        self, owner_client_a: AsyncClient, owner_client_b: AsyncClient
    ):
        ctx = await _seed_finished_shift(owner_client_b)
        r = await owner_client_b.post(
            "/api/v1/liquidations/from-shift", json={"shift_id": ctx["shift_id"]}
        )
        liq_id = r.json()["id"]
        resp = await owner_client_a.get(f"/api/v1/liquidations/{liq_id}")
        assert resp.status_code == 404
