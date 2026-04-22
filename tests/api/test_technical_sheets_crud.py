import uuid

from httpx import AsyncClient


async def _create_model(client: AsyncClient, email: str = "ts_model@a.com") -> str:
    resp = await client.post(
        "/api/v1/users",
        json={
            "email": email,
            "password": "StrongPass123",
            "full_name": "TS Model",
            "role": "MODEL",
        },
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


class TestTechnicalSheetCrud:
    async def test_create_for_model(self, owner_client_a: AsyncClient):
        model_id = await _create_model(owner_client_a)
        resp = await owner_client_a.post(
            "/api/v1/technical-sheets",
            json={
                "model_id": model_id,
                "bio": "Bio here",
                "languages": "en,es",
                "categories": "fit",
                "notes": None,
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["model_id"] == model_id

    async def test_cannot_create_for_non_model_user(self, owner_client_a: AsyncClient):
        resp = await owner_client_a.post(
            "/api/v1/users",
            json={
                "email": "m_monitor@a.com",
                "password": "StrongPass123",
                "full_name": "Monitor X",
                "role": "MONITOR",
            },
        )
        monitor_id = resp.json()["id"]
        bad = await owner_client_a.post(
            "/api/v1/technical-sheets",
            json={"model_id": monitor_id, "bio": "x"},
        )
        assert bad.status_code == 422

    async def test_model_cannot_create_sheet(self, model_client_a: AsyncClient):
        resp = await model_client_a.post(
            "/api/v1/technical-sheets",
            json={"model_id": str(uuid.uuid4()), "bio": "x"},
        )
        assert resp.status_code == 403

    async def test_tenant_isolation(
        self, owner_client_a: AsyncClient, owner_client_b: AsyncClient
    ):
        model_id = await _create_model(owner_client_b, "ts_b@b.com")
        r = await owner_client_b.post(
            "/api/v1/technical-sheets",
            json={"model_id": model_id, "bio": "b"},
        )
        sid = r.json()["id"]
        assert (await owner_client_a.get(f"/api/v1/technical-sheets/{sid}")).status_code == 404

    async def test_update_and_delete(self, owner_client_a: AsyncClient):
        model_id = await _create_model(owner_client_a)
        r = await owner_client_a.post(
            "/api/v1/technical-sheets",
            json={"model_id": model_id, "bio": "orig"},
        )
        sid = r.json()["id"]

        patched = await owner_client_a.patch(
            f"/api/v1/technical-sheets/{sid}", json={"bio": "updated"}
        )
        assert patched.status_code == 200
        assert patched.json()["bio"] == "updated"

        deleted = await owner_client_a.delete(f"/api/v1/technical-sheets/{sid}")
        assert deleted.status_code == 204
        assert (await owner_client_a.get(f"/api/v1/technical-sheets/{sid}")).status_code == 404
