import uuid

from httpx import AsyncClient


class TestUserCreation:
    async def test_owner_creates_monitor(self, owner_client_a: AsyncClient):
        resp = await owner_client_a.post(
            "/api/v1/users",
            json={
                "email": "monitor1@a.com",
                "password": "StrongPass123",
                "full_name": "Monitor One",
                "role": "MONITOR",
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["email"] == "monitor1@a.com"
        assert data["role"] == "MONITOR"
        assert data["is_active"] is True

    async def test_owner_creates_model(self, owner_client_a: AsyncClient):
        resp = await owner_client_a.post(
            "/api/v1/users",
            json={
                "email": "model1@a.com",
                "password": "StrongPass123",
                "full_name": "Model One",
                "role": "MODEL",
            },
        )
        assert resp.status_code == 201

    async def test_cannot_create_owner_role(self, owner_client_a: AsyncClient):
        resp = await owner_client_a.post(
            "/api/v1/users",
            json={
                "email": "second_owner@a.com",
                "password": "StrongPass123",
                "full_name": "Nope",
                "role": "OWNER",
            },
        )
        assert resp.status_code == 422

    async def test_duplicate_email_rejected(self, owner_client_a: AsyncClient):
        payload = {
            "email": "dupe@a.com",
            "password": "StrongPass123",
            "full_name": "Dup User",
            "role": "MONITOR",
        }
        r1 = await owner_client_a.post("/api/v1/users", json=payload)
        assert r1.status_code == 201
        r2 = await owner_client_a.post("/api/v1/users", json=payload)
        assert r2.status_code == 409

    async def test_model_cannot_create_user(self, model_client_a: AsyncClient):
        resp = await model_client_a.post(
            "/api/v1/users",
            json={
                "email": "x@a.com",
                "password": "StrongPass123",
                "full_name": "Xeno",
                "role": "MONITOR",
            },
        )
        assert resp.status_code == 403

    async def test_monitor_cannot_create_user(self, monitor_client_a: AsyncClient):
        resp = await monitor_client_a.post(
            "/api/v1/users",
            json={
                "email": "y@a.com",
                "password": "StrongPass123",
                "full_name": "Yann",
                "role": "MONITOR",
            },
        )
        assert resp.status_code == 403

    async def test_unauthenticated_rejected(self, client: AsyncClient):
        resp = await client.post(
            "/api/v1/users",
            json={
                "email": "z@a.com",
                "password": "StrongPass123",
                "full_name": "Zed",
                "role": "MONITOR",
            },
        )
        assert resp.status_code == 401


class TestUserListAndGet:
    async def test_list_only_returns_own_tenant_users(
        self, owner_client_a: AsyncClient, tenant_b: dict
    ):
        resp = await owner_client_a.get("/api/v1/users")
        assert resp.status_code == 200
        emails = [u["email"] for u in resp.json()["items"]]
        assert "owner_a@example.com" in emails
        assert "owner_b@example.com" not in emails

    async def test_filter_by_role(self, owner_client_a: AsyncClient):
        await owner_client_a.post(
            "/api/v1/users",
            json={
                "email": "m1@a.com",
                "password": "StrongPass123",
                "full_name": "Mod",
                "role": "MODEL",
            },
        )
        resp = await owner_client_a.get("/api/v1/users?role=MODEL")
        data = resp.json()
        assert all(u["role"] == "MODEL" for u in data["items"])


class TestUserUpdate:
    async def test_owner_can_promote_to_admin(self, owner_client_a: AsyncClient):
        r = await owner_client_a.post(
            "/api/v1/users",
            json={
                "email": "promo@a.com",
                "password": "StrongPass123",
                "full_name": "Promo User",
                "role": "MONITOR",
            },
        )
        assert r.status_code == 201, f"create failed: {r.status_code} {r.text}"
        uid = r.json()["id"]
        resp = await owner_client_a.patch(f"/api/v1/users/{uid}", json={"role": "ADMIN"})
        assert resp.status_code == 200
        assert resp.json()["role"] == "ADMIN"

    async def test_owner_account_cannot_be_modified(
        self, owner_client_a: AsyncClient, tenant_a: dict
    ):
        resp = await owner_client_a.patch(
            f"/api/v1/users/{tenant_a['owner_id']}",
            json={"is_active": False},
        )
        assert resp.status_code == 403


class TestTenantIsolation:
    async def test_cannot_read_user_of_other_tenant(
        self, owner_client_a: AsyncClient, tenant_b: dict
    ):
        resp = await owner_client_a.get(f"/api/v1/users/{tenant_b['owner_id']}")
        assert resp.status_code == 404

    async def test_cannot_update_user_of_other_tenant(
        self, owner_client_a: AsyncClient, tenant_b: dict
    ):
        resp = await owner_client_a.patch(
            f"/api/v1/users/{tenant_b['owner_id']}",
            json={"full_name": "Hacked"},
        )
        assert resp.status_code == 404

    async def test_cannot_delete_nonexistent_user(self, owner_client_a: AsyncClient):
        resp = await owner_client_a.delete(f"/api/v1/users/{uuid.uuid4()}")
        assert resp.status_code == 404
