from datetime import UTC, datetime, timedelta
from decimal import Decimal

from httpx import AsyncClient


async def _seed(client: AsyncClient) -> dict:
    mid = (
        await client.post(
            "/api/v1/users",
            json={
                "email": "adv_model@a.com",
                "password": "StrongPass123",
                "full_name": "Adv Model",
                "role": "MODEL",
            },
        )
    ).json()["id"]
    mon = (
        await client.post(
            "/api/v1/users",
            json={
                "email": "adv_mon@a.com",
                "password": "StrongPass123",
                "full_name": "Adv Mon",
                "role": "MONITOR",
            },
        )
    ).json()["id"]
    rch = (
        await client.post(
            "/api/v1/rooms",
            json={
                "name": "CB",
                "platform": "CHATURBATE",
                "url": "https://chaturbate.com/adv/",
            },
        )
    ).json()["id"]
    rst = (
        await client.post(
            "/api/v1/rooms",
            json={
                "name": "SC",
                "platform": "STRIPCHAT",
                "url": "https://stripchat.com/adv/",
            },
        )
    ).json()["id"]

    base = datetime.now(UTC).replace(microsecond=0) - timedelta(days=3)
    for i, (rid, usd) in enumerate([(rch, "40.00"), (rch, "20.00"), (rst, "30.00")]):
        r = await client.post(
            "/api/v1/shifts",
            json={
                "model_id": mid,
                "room_id": rid,
                "monitor_id": mon,
                "start_time": (base + timedelta(days=i)).isoformat(),
                "end_time": (base + timedelta(days=i, hours=1)).isoformat(),
            },
        )
        sid = r.json()["id"]
        await client.patch(
            f"/api/v1/shifts/{sid}",
            json={"status": "FINISHED", "tokens_earned": 500, "usd_earned": usd},
        )
    return {"model_id": mid, "monitor_id": mon}


class TestAdvancedMetrics:
    async def test_revenue_by_platform(self, owner_client_a: AsyncClient):
        await _seed(owner_client_a)
        resp = await owner_client_a.get("/api/v1/metrics/revenue-by-platform")
        assert resp.status_code == 200
        items = resp.json()["items"]
        assert len(items) == 2
        # CHATURBATE should be first: 40 + 20 = 60 USD
        assert items[0]["platform"] == "CHATURBATE"
        assert Decimal(items[0]["total_usd"]) == Decimal("60.00")

    async def test_daily_revenue_range(self, owner_client_a: AsyncClient):
        await _seed(owner_client_a)
        today = datetime.now(UTC).date()
        date_from = (today - timedelta(days=4)).isoformat()
        date_to = today.isoformat()
        resp = await owner_client_a.get(
            f"/api/v1/metrics/daily-revenue?date_from={date_from}&date_to={date_to}"
        )
        items = resp.json()["items"]
        assert len(items) == 3

    async def test_model_overview_requires_model_role(self, owner_client_a: AsyncClient):
        resp = await owner_client_a.get("/api/v1/metrics/model/overview")
        assert resp.status_code == 403

    async def test_model_overview_happy_path(
        self,
        owner_client_a: AsyncClient,
        tenant_a: dict,
    ):
        # Login as the model we'll seed for.
        import uuid

        from httpx import ASGITransport

        from app.core.security import hash_password
        from app.main import app
        from app.models.user import Role, User
        from tests.conftest import TestingSession

        async with TestingSession() as s:
            user = User(
                id=uuid.uuid4(),
                tenant_id=uuid.UUID(tenant_a["tenant_id"]),
                email="own_model@a.com",
                hashed_password=hash_password("StrongPass123"),
                full_name="Own Model",
                role=Role.MODEL,
            )
            s.add(user)
            await s.commit()
            user_id = str(user.id)

        # Create a room + finished shift for this model via OWNER.
        rid = (
            await owner_client_a.post(
                "/api/v1/rooms",
                json={
                    "name": "ModRoom",
                    "platform": "CHATURBATE",
                    "url": "https://chaturbate.com/modroom/",
                },
            )
        ).json()["id"]
        base = datetime.now(UTC).replace(microsecond=0)
        sh = await owner_client_a.post(
            "/api/v1/shifts",
            json={
                "model_id": user_id,
                "room_id": rid,
                "start_time": base.isoformat(),
                "end_time": (base + timedelta(hours=1)).isoformat(),
            },
        )
        sid = sh.json()["id"]
        await owner_client_a.patch(
            f"/api/v1/shifts/{sid}",
            json={"status": "FINISHED", "tokens_earned": 800, "usd_earned": "40.00"},
        )

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as mc:
            login = await mc.post(
                "/api/v1/auth/login",
                json={"email": "own_model@a.com", "password": "StrongPass123"},
            )
            assert login.status_code == 200
            resp = await mc.get("/api/v1/metrics/model/overview")
            assert resp.status_code == 200
            data = resp.json()
            assert data["total_shifts"] == 1
            assert Decimal(data["total_usd"]) == Decimal("40.00")
