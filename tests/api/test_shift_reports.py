from datetime import UTC, datetime, timedelta

from httpx import AsyncClient

ROOM_PAYLOAD = {
    "name": "R for reports",
    "platform": "CHATURBATE",
    "url": "https://chaturbate.com/reports/",
}


async def _finished_shift(client: AsyncClient) -> str:
    mid = (
        await client.post(
            "/api/v1/users",
            json={
                "email": "rep_model@a.com",
                "password": "StrongPass123",
                "full_name": "Rep Model",
                "role": "MODEL",
            },
        )
    ).json()["id"]
    rid = (await client.post("/api/v1/rooms", json=ROOM_PAYLOAD)).json()["id"]
    start = datetime.now(UTC).replace(microsecond=0)
    sh = await client.post(
        "/api/v1/shifts",
        json={
            "model_id": mid,
            "room_id": rid,
            "start_time": start.isoformat(),
            "end_time": (start + timedelta(hours=2)).isoformat(),
        },
    )
    sid = sh.json()["id"]
    await client.patch(
        f"/api/v1/shifts/{sid}",
        json={"status": "FINISHED", "tokens_earned": 1200, "usd_earned": "60.00"},
    )
    return sid


class TestShiftReports:
    async def test_report_auto_generated_on_finish(self, owner_client_a: AsyncClient):
        sid = await _finished_shift(owner_client_a)
        resp = await owner_client_a.get(f"/api/v1/shift-reports/by-shift/{sid}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_tokens"] == 1200
        assert data["duration_minutes"] == 120

    async def test_list(self, owner_client_a: AsyncClient):
        await _finished_shift(owner_client_a)
        resp = await owner_client_a.get("/api/v1/shift-reports")
        assert resp.json()["total"] >= 1

    async def test_idempotent_generation(self, owner_client_a: AsyncClient):
        sid = await _finished_shift(owner_client_a)
        # Second FINISHED transition is a no-op; no duplicate report.
        await owner_client_a.patch(f"/api/v1/shifts/{sid}", json={"status": "FINISHED"})
        listing = await owner_client_a.get("/api/v1/shift-reports")
        assert listing.json()["total"] == 1
