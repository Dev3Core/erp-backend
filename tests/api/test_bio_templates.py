from httpx import AsyncClient


class TestBioTemplates:
    async def test_create_sanitizes_dangerous_html(self, owner_client_a: AsyncClient):
        raw = '<p>Hola <script>alert(1)</script></p><iframe src="x"></iframe>'
        r = await owner_client_a.post(
            "/api/v1/bio-templates",
            json={"name": "default", "html_content": raw},
        )
        assert r.status_code == 201
        stored = r.json()["html_content"]
        assert "<script>" not in stored
        assert "<iframe" not in stored
        assert "<p>Hola" in stored

    async def test_sanitize_preview_endpoint(self, owner_client_a: AsyncClient):
        r = await owner_client_a.post(
            "/api/v1/bio-templates/sanitize",
            json={"html_content": "<b>bold</b><script>nope</script>"},
        )
        assert r.status_code == 200
        assert "<script>" not in r.json()["html_content"]

    async def test_model_cannot_create(self, model_client_a: AsyncClient):
        r = await model_client_a.post(
            "/api/v1/bio-templates",
            json={"name": "n", "html_content": "<p>x</p>"},
        )
        assert r.status_code == 403

    async def test_update_and_delete(self, owner_client_a: AsyncClient):
        r = await owner_client_a.post(
            "/api/v1/bio-templates",
            json={"name": "n", "html_content": "<p>one</p>"},
        )
        tid = r.json()["id"]
        upd = await owner_client_a.patch(
            f"/api/v1/bio-templates/{tid}", json={"html_content": "<p>two</p>"}
        )
        assert "two" in upd.json()["html_content"]
        d = await owner_client_a.delete(f"/api/v1/bio-templates/{tid}")
        assert d.status_code == 204
