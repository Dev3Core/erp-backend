from httpx import ASGITransport, AsyncClient

from app.main import app


class TestExtensionAuth:
    async def test_ext_me_with_api_key(self, model_client_a: AsyncClient):
        issued = await model_client_a.post(
            "/api/v1/auth/api-keys", json={"name": "ext", "ttl_hours": 24}
        )
        plaintext = issued.json()["plaintext_key"]

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ext_client:
            resp = await ext_client.get("/api/v1/ext/me", headers={"X-API-Key": plaintext})
            assert resp.status_code == 200
            assert resp.json()["email"] == "model_a@example.com"

    async def test_ext_requires_api_key(self):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ext_client:
            resp = await ext_client.get("/api/v1/ext/me")
            assert resp.status_code == 401

    async def test_ext_rejects_bad_key(self):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ext_client:
            resp = await ext_client.get("/api/v1/ext/me", headers={"X-API-Key": "not-a-real-key"})
            assert resp.status_code == 401

    async def test_ext_bearer_token_works(self, model_client_a: AsyncClient):
        issued = await model_client_a.post("/api/v1/auth/api-keys", json={"ttl_hours": 24})
        plaintext = issued.json()["plaintext_key"]
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ext_client:
            resp = await ext_client.get(
                "/api/v1/ext/me",
                headers={"Authorization": f"Bearer {plaintext}"},
            )
            assert resp.status_code == 200

    async def test_revoked_key_rejected(self, model_client_a: AsyncClient):
        issued = await model_client_a.post("/api/v1/auth/api-keys", json={"ttl_hours": 24})
        plaintext = issued.json()["plaintext_key"]
        await model_client_a.delete(f"/api/v1/auth/api-keys/{issued.json()['id']}")
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ext_client:
            resp = await ext_client.get("/api/v1/ext/me", headers={"X-API-Key": plaintext})
            assert resp.status_code == 401

    async def test_ext_macros(self, model_client_a: AsyncClient):
        await model_client_a.post(
            "/api/v1/macros",
            json={"label": "hi", "content": "hola!", "platform": "CHATURBATE"},
        )
        issued = await model_client_a.post("/api/v1/auth/api-keys", json={"ttl_hours": 24})
        plaintext = issued.json()["plaintext_key"]
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ext_client:
            resp = await ext_client.get("/api/v1/ext/macros", headers={"X-API-Key": plaintext})
            assert resp.status_code == 200
            assert resp.json()["total"] == 1
