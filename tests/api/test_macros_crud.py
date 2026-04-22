from httpx import AsyncClient


class TestMacros:
    async def test_create_and_list(self, model_client_a: AsyncClient):
        r = await model_client_a.post(
            "/api/v1/macros",
            json={
                "label": "hola",
                "content": "hola guapo! bienvenido a mi show",
                "platform": "CHATURBATE",
                "position": 0,
            },
        )
        assert r.status_code == 201
        listing = await model_client_a.get("/api/v1/macros")
        assert listing.json()["total"] == 1
        assert listing.json()["items"][0]["content"].startswith("hola")

    async def test_macros_are_scoped_per_user(
        self, model_client_a: AsyncClient, monitor_client_a: AsyncClient
    ):
        await model_client_a.post("/api/v1/macros", json={"label": "a", "content": "model macro"})
        listing = await monitor_client_a.get("/api/v1/macros")
        assert listing.json()["total"] == 0

    async def test_filter_by_platform(self, model_client_a: AsyncClient):
        await model_client_a.post(
            "/api/v1/macros",
            json={"label": "c", "content": "c msg", "platform": "CHATURBATE"},
        )
        await model_client_a.post(
            "/api/v1/macros",
            json={"label": "s", "content": "s msg", "platform": "STRIPCHAT"},
        )
        listing = await model_client_a.get("/api/v1/macros?platform=CHATURBATE")
        items = listing.json()["items"]
        assert all(m["platform"] == "CHATURBATE" for m in items)

    async def test_update_and_delete(self, model_client_a: AsyncClient):
        r = await model_client_a.post("/api/v1/macros", json={"label": "x", "content": "original"})
        mid = r.json()["id"]
        upd = await model_client_a.patch(f"/api/v1/macros/{mid}", json={"content": "updated"})
        assert upd.json()["content"] == "updated"
        d = await model_client_a.delete(f"/api/v1/macros/{mid}")
        assert d.status_code == 204
