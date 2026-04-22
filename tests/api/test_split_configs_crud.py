from httpx import AsyncClient

BASE_60_40 = {
    "label": "Default 60/40",
    "platform_pct": "50.00",
    "studio_pct": "30.00",
    "model_pct": "20.00",
    "is_default": True,
}


class TestSplitConfigsCrud:
    async def test_create_with_default(self, owner_client_a: AsyncClient):
        resp = await owner_client_a.post("/api/v1/split-configs", json=BASE_60_40)
        assert resp.status_code == 201
        data = resp.json()
        assert data["is_default"] is True
        assert data["label"] == "Default 60/40"

    async def test_pct_sum_validation(self, owner_client_a: AsyncClient):
        resp = await owner_client_a.post(
            "/api/v1/split-configs",
            json={
                "label": "Invalid",
                "platform_pct": "50.00",
                "studio_pct": "30.00",
                "model_pct": "10.00",  # sum = 90
                "is_default": False,
            },
        )
        assert resp.status_code == 422

    async def test_only_one_default_at_a_time(self, owner_client_a: AsyncClient):
        await owner_client_a.post("/api/v1/split-configs", json=BASE_60_40)
        resp2 = await owner_client_a.post(
            "/api/v1/split-configs",
            json={**BASE_60_40, "label": "Second", "is_default": True},
        )
        assert resp2.status_code == 201

        listing = await owner_client_a.get("/api/v1/split-configs")
        defaults = [c for c in listing.json()["items"] if c["is_default"]]
        assert len(defaults) == 1
        assert defaults[0]["label"] == "Second"

    async def test_model_cannot_create(self, model_client_a: AsyncClient):
        resp = await model_client_a.post("/api/v1/split-configs", json=BASE_60_40)
        assert resp.status_code == 403

    async def test_delete(self, owner_client_a: AsyncClient):
        r = await owner_client_a.post("/api/v1/split-configs", json=BASE_60_40)
        cid = r.json()["id"]
        resp = await owner_client_a.delete(f"/api/v1/split-configs/{cid}")
        assert resp.status_code == 204
        got = await owner_client_a.get(f"/api/v1/split-configs/{cid}")
        assert got.status_code == 404

    async def test_tenant_isolation(
        self, owner_client_a: AsyncClient, owner_client_b: AsyncClient
    ):
        r = await owner_client_b.post("/api/v1/split-configs", json=BASE_60_40)
        cid = r.json()["id"]
        assert (await owner_client_a.get(f"/api/v1/split-configs/{cid}")).status_code == 404
        listing = await owner_client_a.get("/api/v1/split-configs")
        assert listing.json()["total"] == 0
