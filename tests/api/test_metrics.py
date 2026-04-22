from datetime import UTC, datetime, timedelta
from decimal import Decimal

from httpx import AsyncClient

ROOM_PAYLOAD = {
    "name": "Metrics Room",
    "platform": "CHATURBATE",
    "url": "https://chaturbate.com/metrics/",
}


async def _seed_dataset(client: AsyncClient) -> None:
    # Two models, one monitor, two rooms, a few finished shifts.
    mr1 = (
        await client.post(
            "/api/v1/users",
            json={
                "email": "m1@a.com",
                "password": "StrongPass123",
                "full_name": "M One",
                "role": "MODEL",
            },
        )
    ).json()["id"]
    mr2 = (
        await client.post(
            "/api/v1/users",
            json={
                "email": "m2@a.com",
                "password": "StrongPass123",
                "full_name": "M Two",
                "role": "MODEL",
            },
        )
    ).json()["id"]
    mon = (
        await client.post(
            "/api/v1/users",
            json={
                "email": "mon1@a.com",
                "password": "StrongPass123",
                "full_name": "Mon One",
                "role": "MONITOR",
            },
        )
    ).json()["id"]
    room = (await client.post("/api/v1/rooms", json=ROOM_PAYLOAD)).json()["id"]

    base = datetime.now(UTC).replace(microsecond=0) - timedelta(days=1)
    specs = [
        (mr1, 1500, "75.00"),
        (mr1, 2000, "100.00"),
        (mr2, 500, "25.00"),
    ]
    for i, (mid, tokens, usd) in enumerate(specs):
        r = await client.post(
            "/api/v1/shifts",
            json={
                "model_id": mid,
                "room_id": room,
                "monitor_id": mon,
                "start_time": (base + timedelta(hours=i)).isoformat(),
                "end_time": (base + timedelta(hours=i + 1)).isoformat(),
            },
        )
        sid = r.json()["id"]
        await client.patch(
            f"/api/v1/shifts/{sid}",
            json={"status": "FINISHED", "tokens_earned": tokens, "usd_earned": usd},
        )


class TestMetrics:
    async def test_overview_aggregates_finished_shifts(self, owner_client_a: AsyncClient):
        await _seed_dataset(owner_client_a)
        resp = await owner_client_a.get("/api/v1/metrics/overview")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_shifts"] == 3
        assert data["total_tokens"] == 4000
        assert Decimal(data["total_usd"]) == Decimal("200.00")
        assert data["liquidations_pending"] == 0
        assert data["liquidations_approved"] == 0
        assert data["liquidations_paid"] == 0

    async def test_revenue_by_model_ranks_by_usd(self, owner_client_a: AsyncClient):
        await _seed_dataset(owner_client_a)
        resp = await owner_client_a.get("/api/v1/metrics/revenue-by-model")
        assert resp.status_code == 200
        items = resp.json()["items"]
        assert len(items) == 2
        # mr1 has 175.00, mr2 has 25.00 -> mr1 first
        assert items[0]["email"] == "m1@a.com"
        assert Decimal(items[0]["total_usd"]) == Decimal("175.00")
        assert items[1]["email"] == "m2@a.com"

    async def test_revenue_by_monitor(self, owner_client_a: AsyncClient):
        await _seed_dataset(owner_client_a)
        resp = await owner_client_a.get("/api/v1/metrics/revenue-by-monitor")
        assert resp.status_code == 200
        items = resp.json()["items"]
        assert len(items) == 1
        assert items[0]["email"] == "mon1@a.com"
        assert Decimal(items[0]["total_usd"]) == Decimal("200.00")
        assert items[0]["total_shifts"] == 3

    async def test_model_cannot_access_metrics(self, model_client_a: AsyncClient):
        resp = await model_client_a.get("/api/v1/metrics/overview")
        assert resp.status_code == 403

    async def test_tenant_isolation_on_metrics(
        self, owner_client_a: AsyncClient, owner_client_b: AsyncClient
    ):
        await _seed_dataset(owner_client_b)
        resp = await owner_client_a.get("/api/v1/metrics/overview")
        data = resp.json()
        assert data["total_shifts"] == 0
        assert Decimal(data["total_usd"]) == Decimal("0")
