from httpx import AsyncClient


class TestSalaryAdvances:
    async def test_model_requests_and_owner_approves(
        self, owner_client_a: AsyncClient, model_client_a: AsyncClient
    ):
        r = await model_client_a.post(
            "/api/v1/salary-advances",
            json={"amount_cop": "500000.00", "reason": "familia"},
        )
        assert r.status_code == 201
        rid = r.json()["id"]
        assert r.json()["status"] == "PENDING"

        mine = await model_client_a.get("/api/v1/salary-advances/mine")
        assert mine.json()["total"] == 1

        review = await owner_client_a.patch(
            f"/api/v1/salary-advances/{rid}/review",
            json={"status": "APPROVED", "review_notes": "ok"},
        )
        assert review.status_code == 200 and review.json()["status"] == "APPROVED"

    async def test_model_cannot_review(self, model_client_a: AsyncClient):
        r = await model_client_a.post("/api/v1/salary-advances", json={"amount_cop": "100000.00"})
        rid = r.json()["id"]
        resp = await model_client_a.patch(
            f"/api/v1/salary-advances/{rid}/review",
            json={"status": "APPROVED"},
        )
        assert resp.status_code == 403

    async def test_invalid_transition(
        self, owner_client_a: AsyncClient, model_client_a: AsyncClient
    ):
        r = await model_client_a.post("/api/v1/salary-advances", json={"amount_cop": "100000.00"})
        rid = r.json()["id"]
        # PENDING -> PAID is not allowed (must go through APPROVED)
        resp = await owner_client_a.patch(
            f"/api/v1/salary-advances/{rid}/review",
            json={"status": "PAID"},
        )
        assert resp.status_code == 422

    async def test_model_only_sees_own_requests(
        self, owner_client_a: AsyncClient, model_client_a: AsyncClient
    ):
        await model_client_a.post("/api/v1/salary-advances", json={"amount_cop": "111111.00"})
        # Owner creates one from their own side (owner is OWNER role, but request endpoint
        # accepts any authed user).
        await owner_client_a.post("/api/v1/salary-advances", json={"amount_cop": "222222.00"})
        listing = await model_client_a.get("/api/v1/salary-advances/mine")
        items = listing.json()["items"]
        assert len(items) == 1
        assert items[0]["amount_cop"] == "111111.00"


class TestSalaryAdvanceTenantIso:
    async def test_cross_tenant_hidden(
        self, owner_client_a: AsyncClient, owner_client_b: AsyncClient
    ):
        b_req = await owner_client_b.post(
            "/api/v1/salary-advances", json={"amount_cop": "99999.00"}
        )
        rid = b_req.json()["id"]
        resp = await owner_client_a.get(f"/api/v1/salary-advances/{rid}")
        assert resp.status_code == 404
