from datetime import UTC, datetime, timedelta

from httpx import AsyncClient

ROOM_PAYLOAD = {
    "name": "Chat Room",
    "platform": "CHATURBATE",
    "url": "https://chaturbate.com/chat/",
}


async def _chat_setup(owner: AsyncClient) -> tuple[str, str, str]:
    """Return (shift_id, model_id, monitor_id) with monitor_a + model_a already
    seeded by the fixtures."""
    model_id = (
        await owner.post(
            "/api/v1/users",
            json={
                "email": "chat_model@a.com",
                "password": "StrongPass123",
                "full_name": "Chat Model",
                "role": "MODEL",
            },
        )
    ).json()["id"]
    monitor_id = (
        await owner.post(
            "/api/v1/users",
            json={
                "email": "chat_mon@a.com",
                "password": "StrongPass123",
                "full_name": "Chat Mon",
                "role": "MONITOR",
            },
        )
    ).json()["id"]
    room_id = (await owner.post("/api/v1/rooms", json=ROOM_PAYLOAD)).json()["id"]
    base = datetime.now(UTC).replace(microsecond=0)
    sh = await owner.post(
        "/api/v1/shifts",
        json={
            "model_id": model_id,
            "room_id": room_id,
            "monitor_id": monitor_id,
            "start_time": base.isoformat(),
            "end_time": (base + timedelta(hours=2)).isoformat(),
        },
    )
    return sh.json()["id"], model_id, monitor_id


class TestChat:
    async def test_post_and_list_messages_as_owner(self, owner_client_a: AsyncClient):
        shift_id, _, _ = await _chat_setup(owner_client_a)
        r = await owner_client_a.post(
            f"/api/v1/chat/shift/{shift_id}/messages",
            json={"body": "hola equipo"},
        )
        assert r.status_code == 201
        listing = await owner_client_a.get(f"/api/v1/chat/shift/{shift_id}/messages")
        assert listing.json()["total"] == 1

    async def test_non_participant_gets_403(
        self, owner_client_a: AsyncClient, model_client_a: AsyncClient
    ):
        # Model in tenant A but not the one assigned to this shift.
        shift_id, _, _ = await _chat_setup(owner_client_a)
        resp = await model_client_a.post(
            f"/api/v1/chat/shift/{shift_id}/messages",
            json={"body": "hi"},
        )
        assert resp.status_code == 403

    async def test_tenant_isolation(
        self, owner_client_a: AsyncClient, owner_client_b: AsyncClient
    ):
        shift_id, _, _ = await _chat_setup(owner_client_b)
        resp = await owner_client_a.get(f"/api/v1/chat/shift/{shift_id}/messages")
        assert resp.status_code == 404
