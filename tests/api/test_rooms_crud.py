import uuid

from httpx import AsyncClient

ROOM_PAYLOAD = {
    "name": "Test Room",
    "platform": "CHATURBATE",
    "url": "https://chaturbate.com/testroom/",
}


class TestRoomsCrud:
    async def test_owner_creates_room(self, owner_client_a: AsyncClient):
        resp = await owner_client_a.post("/api/v1/rooms", json=ROOM_PAYLOAD)
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "Test Room"
        assert data["platform"] == "CHATURBATE"
        assert data["is_active"] is True

    async def test_duplicate_url_per_platform_rejected(self, owner_client_a: AsyncClient):
        r1 = await owner_client_a.post("/api/v1/rooms", json=ROOM_PAYLOAD)
        assert r1.status_code == 201
        r2 = await owner_client_a.post("/api/v1/rooms", json=ROOM_PAYLOAD)
        assert r2.status_code == 409

    async def test_model_cannot_create_room(self, model_client_a: AsyncClient):
        resp = await model_client_a.post("/api/v1/rooms", json=ROOM_PAYLOAD)
        assert resp.status_code == 403

    async def test_model_can_list_rooms(
        self, owner_client_a: AsyncClient, model_client_a: AsyncClient
    ):
        await owner_client_a.post("/api/v1/rooms", json=ROOM_PAYLOAD)
        resp = await model_client_a.get("/api/v1/rooms")
        assert resp.status_code == 200
        assert resp.json()["total"] >= 1

    async def test_filter_by_platform(self, owner_client_a: AsyncClient):
        await owner_client_a.post("/api/v1/rooms", json=ROOM_PAYLOAD)
        await owner_client_a.post(
            "/api/v1/rooms",
            json={**ROOM_PAYLOAD, "platform": "STRIPCHAT", "url": "https://stripchat.com/x/"},
        )
        resp = await owner_client_a.get("/api/v1/rooms?platform=CHATURBATE")
        items = resp.json()["items"]
        assert all(r["platform"] == "CHATURBATE" for r in items)

    async def test_update_status(self, owner_client_a: AsyncClient):
        r = await owner_client_a.post("/api/v1/rooms", json=ROOM_PAYLOAD)
        rid = r.json()["id"]
        resp = await owner_client_a.patch(f"/api/v1/rooms/{rid}", json={"status": "ONLINE"})
        assert resp.status_code == 200
        assert resp.json()["status"] == "ONLINE"

    async def test_delete_is_soft(self, owner_client_a: AsyncClient):
        r = await owner_client_a.post("/api/v1/rooms", json=ROOM_PAYLOAD)
        rid = r.json()["id"]
        resp = await owner_client_a.delete(f"/api/v1/rooms/{rid}")
        assert resp.status_code == 204
        got = await owner_client_a.get(f"/api/v1/rooms/{rid}")
        assert got.status_code == 200
        assert got.json()["is_active"] is False


class TestRoomsTenantIsolation:
    async def test_cannot_see_other_tenant_room(
        self, owner_client_a: AsyncClient, owner_client_b: AsyncClient
    ):
        r = await owner_client_b.post("/api/v1/rooms", json=ROOM_PAYLOAD)
        assert r.status_code == 201
        rid = r.json()["id"]

        resp = await owner_client_a.get(f"/api/v1/rooms/{rid}")
        assert resp.status_code == 404

        resp2 = await owner_client_a.get("/api/v1/rooms")
        ids = [x["id"] for x in resp2.json()["items"]]
        assert rid not in ids

    async def test_cannot_modify_other_tenant_room(
        self, owner_client_a: AsyncClient, owner_client_b: AsyncClient
    ):
        r = await owner_client_b.post("/api/v1/rooms", json=ROOM_PAYLOAD)
        rid = r.json()["id"]
        resp = await owner_client_a.patch(f"/api/v1/rooms/{rid}", json={"name": "Hacked"})
        assert resp.status_code == 404

    async def test_unauth_unprotected_endpoint_rejected(self, client: AsyncClient):
        assert (await client.get("/api/v1/rooms")).status_code == 401
        assert (await client.post("/api/v1/rooms", json=ROOM_PAYLOAD)).status_code == 401
        assert (await client.get(f"/api/v1/rooms/{uuid.uuid4()}")).status_code == 401
