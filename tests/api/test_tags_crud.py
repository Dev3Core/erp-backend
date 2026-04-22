from httpx import AsyncClient

ROOM_PAYLOAD = {
    "name": "Tags Room",
    "platform": "CHATURBATE",
    "url": "https://chaturbate.com/tags/",
}


async def _room(client: AsyncClient) -> str:
    return (await client.post("/api/v1/rooms", json=ROOM_PAYLOAD)).json()["id"]


class TestTags:
    async def test_create_tag(self, owner_client_a: AsyncClient):
        rid = await _room(owner_client_a)
        resp = await owner_client_a.post(
            "/api/v1/tags",
            json={"room_id": rid, "value": "fit", "platform": "CHATURBATE"},
        )
        assert resp.status_code == 201

    async def test_unique_per_room_and_platform(self, owner_client_a: AsyncClient):
        rid = await _room(owner_client_a)
        await owner_client_a.post(
            "/api/v1/tags",
            json={"room_id": rid, "value": "latina", "platform": "CHATURBATE"},
        )
        dup = await owner_client_a.post(
            "/api/v1/tags",
            json={"room_id": rid, "value": "latina", "platform": "CHATURBATE"},
        )
        assert dup.status_code == 409

    async def test_invalid_value_rejected(self, owner_client_a: AsyncClient):
        rid = await _room(owner_client_a)
        bad = await owner_client_a.post(
            "/api/v1/tags",
            json={"room_id": rid, "value": "has space", "platform": "CHATURBATE"},
        )
        assert bad.status_code == 422

    async def test_monitor_can_manage_tags(
        self, monitor_client_a: AsyncClient, owner_client_a: AsyncClient
    ):
        rid = await _room(owner_client_a)
        resp = await monitor_client_a.post(
            "/api/v1/tags",
            json={"room_id": rid, "value": "premium", "platform": "CHATURBATE"},
        )
        assert resp.status_code == 201

    async def test_model_cannot_create(
        self, model_client_a: AsyncClient, owner_client_a: AsyncClient
    ):
        rid = await _room(owner_client_a)
        resp = await model_client_a.post(
            "/api/v1/tags",
            json={"room_id": rid, "value": "x", "platform": "CHATURBATE"},
        )
        assert resp.status_code == 403
