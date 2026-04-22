from datetime import UTC, datetime

from httpx import AsyncClient


class TestApiKeys:
    async def test_issue_returns_plaintext_once(self, model_client_a: AsyncClient):
        resp = await model_client_a.post(
            "/api/v1/auth/api-keys", json={"name": "extension", "ttl_hours": 24}
        )
        assert resp.status_code == 201
        data = resp.json()
        assert "plaintext_key" in data and len(data["plaintext_key"]) >= 32
        assert data["prefix"] == data["plaintext_key"][:12]

        # List never exposes plaintext
        listing = await model_client_a.get("/api/v1/auth/api-keys")
        items = listing.json()["items"]
        assert len(items) == 1
        assert "plaintext_key" not in items[0]
        assert items[0]["prefix"] == data["prefix"]

    async def test_keys_are_scoped_per_user(
        self,
        model_client_a: AsyncClient,
        owner_client_a: AsyncClient,
    ):
        await model_client_a.post("/api/v1/auth/api-keys", json={"ttl_hours": 24})
        # Owner sees only their own keys (none) not the model's
        resp = await owner_client_a.get("/api/v1/auth/api-keys")
        assert resp.json()["total"] == 0

    async def test_revoke_own_key(self, model_client_a: AsyncClient):
        r = await model_client_a.post("/api/v1/auth/api-keys", json={"ttl_hours": 24})
        kid = r.json()["id"]
        resp = await model_client_a.delete(f"/api/v1/auth/api-keys/{kid}")
        assert resp.status_code == 204

        listing = await model_client_a.get("/api/v1/auth/api-keys?include_revoked=true")
        revoked = listing.json()["items"][0]
        assert revoked["revoked_at"] is not None

    async def test_cannot_revoke_other_users_key(
        self, model_client_a: AsyncClient, monitor_client_a: AsyncClient
    ):
        r = await model_client_a.post("/api/v1/auth/api-keys", json={"ttl_hours": 24})
        kid = r.json()["id"]
        resp = await monitor_client_a.delete(f"/api/v1/auth/api-keys/{kid}")
        assert resp.status_code == 403

    async def test_expiry_in_future(self, model_client_a: AsyncClient):
        resp = await model_client_a.post("/api/v1/auth/api-keys", json={"ttl_hours": 1})
        data = resp.json()
        expires = datetime.fromisoformat(data["expires_at"].replace("Z", "+00:00"))
        assert expires > datetime.now(UTC)
