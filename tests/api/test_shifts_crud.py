from datetime import UTC, datetime, timedelta

from httpx import AsyncClient

ROOM_PAYLOAD = {
    "name": "Room for shifts",
    "platform": "CHATURBATE",
    "url": "https://chaturbate.com/shifts/",
}


async def _setup_model_and_room(client: AsyncClient) -> tuple[str, str]:
    mr = await client.post(
        "/api/v1/users",
        json={
            "email": "shift_model@a.com",
            "password": "StrongPass123",
            "full_name": "Shift Model",
            "role": "MODEL",
        },
    )
    assert mr.status_code == 201, mr.text
    rr = await client.post("/api/v1/rooms", json=ROOM_PAYLOAD)
    assert rr.status_code == 201, rr.text
    return mr.json()["id"], rr.json()["id"]


class TestShiftsCrud:
    async def test_create_shift(self, owner_client_a: AsyncClient):
        model_id, room_id = await _setup_model_and_room(owner_client_a)
        start = datetime.now(UTC).replace(microsecond=0)
        resp = await owner_client_a.post(
            "/api/v1/shifts",
            json={
                "model_id": model_id,
                "room_id": room_id,
                "start_time": start.isoformat(),
                "end_time": (start + timedelta(hours=4)).isoformat(),
            },
        )
        assert resp.status_code == 201, resp.text
        data = resp.json()
        assert data["status"] == "SCHEDULED"
        assert data["tokens_earned"] == 0

    async def test_end_before_start_rejected(self, owner_client_a: AsyncClient):
        model_id, room_id = await _setup_model_and_room(owner_client_a)
        start = datetime.now(UTC).replace(microsecond=0)
        resp = await owner_client_a.post(
            "/api/v1/shifts",
            json={
                "model_id": model_id,
                "room_id": room_id,
                "start_time": start.isoformat(),
                "end_time": (start - timedelta(hours=1)).isoformat(),
            },
        )
        assert resp.status_code == 422

    async def test_cannot_schedule_non_model_as_model(self, owner_client_a: AsyncClient):
        mr = await owner_client_a.post(
            "/api/v1/users",
            json={
                "email": "shift_monitor@a.com",
                "password": "StrongPass123",
                "full_name": "Mon",
                "role": "MONITOR",
            },
        )
        monitor_id = mr.json()["id"]
        rr = await owner_client_a.post("/api/v1/rooms", json=ROOM_PAYLOAD)
        room_id = rr.json()["id"]

        resp = await owner_client_a.post(
            "/api/v1/shifts",
            json={
                "model_id": monitor_id,
                "room_id": room_id,
                "start_time": datetime.now(UTC).isoformat(),
            },
        )
        assert resp.status_code == 422

    async def test_update_status_and_earnings(self, owner_client_a: AsyncClient):
        model_id, room_id = await _setup_model_and_room(owner_client_a)
        r = await owner_client_a.post(
            "/api/v1/shifts",
            json={
                "model_id": model_id,
                "room_id": room_id,
                "start_time": datetime.now(UTC).isoformat(),
            },
        )
        sid = r.json()["id"]
        resp = await owner_client_a.patch(
            f"/api/v1/shifts/{sid}",
            json={"status": "FINISHED", "tokens_earned": 1500, "usd_earned": "75.00"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "FINISHED"
        assert data["tokens_earned"] == 1500

    async def test_tenant_isolation(
        self, owner_client_a: AsyncClient, owner_client_b: AsyncClient
    ):
        mid, rid = await _setup_model_and_room(owner_client_b)
        r = await owner_client_b.post(
            "/api/v1/shifts",
            json={
                "model_id": mid,
                "room_id": rid,
                "start_time": datetime.now(UTC).isoformat(),
            },
        )
        sid = r.json()["id"]
        assert (await owner_client_a.get(f"/api/v1/shifts/{sid}")).status_code == 404
        listing = await owner_client_a.get("/api/v1/shifts")
        assert listing.json()["items"] == []
