from datetime import date

from httpx import AsyncClient


async def _create_monitor(client: AsyncClient, email: str = "sal_mon@a.com") -> str:
    r = await client.post(
        "/api/v1/users",
        json={
            "email": email,
            "password": "StrongPass123",
            "full_name": "Salary Monitor",
            "role": "MONITOR",
        },
    )
    assert r.status_code == 201, r.text
    return r.json()["id"]


class TestMonitorSalariesCrud:
    async def test_create_and_list(self, owner_client_a: AsyncClient):
        mid = await _create_monitor(owner_client_a)
        r = await owner_client_a.post(
            "/api/v1/monitor-salaries",
            json={
                "monitor_id": mid,
                "amount_cop": "2500000.00",
                "effective_from": "2026-01-01",
                "notes": "contrato inicial",
            },
        )
        assert r.status_code == 201
        listing = await owner_client_a.get(f"/api/v1/monitor-salaries?monitor_id={mid}")
        assert listing.json()["total"] == 1

    async def test_history_via_multiple_rows(self, owner_client_a: AsyncClient):
        mid = await _create_monitor(owner_client_a)
        for d, amt in [("2026-01-01", "2500000"), ("2026-03-01", "2800000")]:
            await owner_client_a.post(
                "/api/v1/monitor-salaries",
                json={"monitor_id": mid, "amount_cop": f"{amt}.00", "effective_from": d},
            )

        cur = await owner_client_a.get(f"/api/v1/monitor-salaries/current/{mid}?as_of=2026-02-15")
        assert cur.json()["amount_cop"] == "2500000.00"
        cur2 = await owner_client_a.get(f"/api/v1/monitor-salaries/current/{mid}?as_of=2026-04-01")
        assert cur2.json()["amount_cop"] == "2800000.00"

    async def test_cannot_assign_to_non_monitor(self, owner_client_a: AsyncClient):
        r = await owner_client_a.post(
            "/api/v1/users",
            json={
                "email": "xmodel@a.com",
                "password": "StrongPass123",
                "full_name": "Model X",
                "role": "MODEL",
            },
        )
        model_id = r.json()["id"]
        resp = await owner_client_a.post(
            "/api/v1/monitor-salaries",
            json={
                "monitor_id": model_id,
                "amount_cop": "1000000.00",
                "effective_from": str(date.today()),
            },
        )
        assert resp.status_code == 422

    async def test_model_cannot_create(self, model_client_a: AsyncClient):
        resp = await model_client_a.post(
            "/api/v1/monitor-salaries",
            json={
                "monitor_id": "00000000-0000-0000-0000-000000000000",
                "amount_cop": "1000000.00",
                "effective_from": "2026-01-01",
            },
        )
        assert resp.status_code == 403

    async def test_tenant_isolation(
        self, owner_client_a: AsyncClient, owner_client_b: AsyncClient
    ):
        mid = await _create_monitor(owner_client_b, "sal_mon_b@b.com")
        r = await owner_client_b.post(
            "/api/v1/monitor-salaries",
            json={
                "monitor_id": mid,
                "amount_cop": "2000000.00",
                "effective_from": "2026-01-01",
            },
        )
        sid = r.json()["id"]
        resp = await owner_client_a.get("/api/v1/monitor-salaries")
        assert resp.json()["total"] == 0
        resp2 = await owner_client_a.delete(f"/api/v1/monitor-salaries/{sid}")
        assert resp2.status_code == 404
