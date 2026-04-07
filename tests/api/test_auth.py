import pyotp
from httpx import AsyncClient


async def _login_request(client: AsyncClient, email: str, password: str):
    return await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )


class TestRegister:
    async def test_register_success(self, client: AsyncClient):
        resp = await client.post(
            "/api/v1/auth/register",
            json={
                "studio_name": "My Studio",
                "full_name": "John Doe",
                "email": "john@example.com",
                "password": "StrongPass123",
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["email"] == "john@example.com"
        assert data["studio_slug"] == "my-studio"
        assert "tenant_id" in data
        assert "user_id" in data

    async def test_register_duplicate_email(self, client: AsyncClient):
        payload = {
            "studio_name": "Studio A",
            "full_name": "Jane",
            "email": "dupe@example.com",
            "password": "StrongPass123",
        }
        resp1 = await client.post("/api/v1/auth/register", json=payload)
        assert resp1.status_code == 201

        payload["studio_name"] = "Studio B"
        resp2 = await client.post("/api/v1/auth/register", json=payload)
        assert resp2.status_code == 409

    async def test_register_weak_password(self, client: AsyncClient):
        resp = await client.post(
            "/api/v1/auth/register",
            json={
                "studio_name": "Studio",
                "full_name": "Test",
                "email": "weak@example.com",
                "password": "short",
            },
        )
        assert resp.status_code == 422

    async def test_register_invalid_email(self, client: AsyncClient):
        resp = await client.post(
            "/api/v1/auth/register",
            json={
                "studio_name": "Studio",
                "full_name": "Test",
                "email": "not-an-email",
                "password": "StrongPass123",
            },
        )
        assert resp.status_code == 422

    async def test_register_generates_unique_slug(self, client: AsyncClient):
        base = {
            "full_name": "Test",
            "password": "StrongPass123",
            "studio_name": "Same Name",
        }
        r1 = await client.post(
            "/api/v1/auth/register",
            json={**base, "email": "a@example.com"},
        )
        r2 = await client.post(
            "/api/v1/auth/register",
            json={**base, "email": "b@example.com"},
        )
        assert r1.status_code == 201
        assert r2.status_code == 201
        assert r1.json()["studio_slug"] != r2.json()["studio_slug"]


class TestLogin:
    async def test_login_success(self, client: AsyncClient, seed_tenant_and_owner: dict):
        seed = seed_tenant_and_owner
        resp = await _login_request(client, seed["email"], seed["password"])
        assert resp.status_code == 200
        data = resp.json()
        assert data["email"] == seed["email"]
        assert data["role"] == "OWNER"
        assert "access_token" in resp.cookies
        assert "refresh_token" in resp.cookies

    async def test_login_wrong_password(self, client: AsyncClient, seed_tenant_and_owner: dict):
        resp = await _login_request(client, seed_tenant_and_owner["email"], "WrongPass")
        assert resp.status_code == 401

    async def test_login_nonexistent_email(self, client: AsyncClient):
        resp = await _login_request(client, "nobody@example.com", "Whatever123")
        assert resp.status_code == 401

    async def test_login_inactive_tenant(self, client: AsyncClient, inactive_tenant_user: dict):
        seed = inactive_tenant_user
        resp = await _login_request(client, seed["email"], seed["password"])
        assert resp.status_code == 401
        detail = resp.json()["detail"].lower()
        assert "suspended" in detail or "contact" in detail


class TestRefresh:
    async def test_refresh_success(self, client: AsyncClient, seed_tenant_and_owner: dict):
        seed = seed_tenant_and_owner
        login_resp = await _login_request(client, seed["email"], seed["password"])
        client.cookies.set("refresh_token", login_resp.cookies["refresh_token"])

        resp = await client.post("/api/v1/auth/refresh")
        assert resp.status_code == 200
        assert "access_token" in resp.cookies

    async def test_refresh_no_token(self, client: AsyncClient):
        resp = await client.post("/api/v1/auth/refresh")
        assert resp.status_code == 401

    async def test_refresh_reuse_blocked(self, client: AsyncClient, seed_tenant_and_owner: dict):
        seed = seed_tenant_and_owner
        login_resp = await _login_request(client, seed["email"], seed["password"])
        old_refresh = login_resp.cookies["refresh_token"]
        client.cookies.set("refresh_token", old_refresh)

        resp1 = await client.post("/api/v1/auth/refresh")
        assert resp1.status_code == 200

        client.cookies.set("refresh_token", old_refresh)
        resp2 = await client.post("/api/v1/auth/refresh")
        assert resp2.status_code == 401


class TestLogout:
    async def test_logout_success(self, client: AsyncClient, seed_tenant_and_owner: dict):
        seed = seed_tenant_and_owner
        login_resp = await _login_request(client, seed["email"], seed["password"])
        client.cookies.set("access_token", login_resp.cookies["access_token"])
        client.cookies.set("refresh_token", login_resp.cookies["refresh_token"])

        resp = await client.post("/api/v1/auth/logout")
        assert resp.status_code == 200

    async def test_logout_without_tokens(self, client: AsyncClient):
        resp = await client.post("/api/v1/auth/logout")
        assert resp.status_code == 200


class TestMFA:
    async def _login(self, client: AsyncClient, seed: dict) -> None:
        resp = await _login_request(client, seed["email"], seed["password"])
        client.cookies.set("access_token", resp.cookies["access_token"])
        client.cookies.set("refresh_token", resp.cookies["refresh_token"])

    async def test_mfa_setup(self, client: AsyncClient, seed_tenant_and_owner: dict):
        await self._login(client, seed_tenant_and_owner)

        resp = await client.post("/api/v1/auth/mfa/setup")
        assert resp.status_code == 200
        data = resp.json()
        assert "otpauth://" in data["qr_uri"]
        assert len(data["secret"]) > 0

    async def test_mfa_verify(self, client: AsyncClient, seed_tenant_and_owner: dict):
        await self._login(client, seed_tenant_and_owner)

        setup_resp = await client.post("/api/v1/auth/mfa/setup")
        secret = setup_resp.json()["secret"]

        totp = pyotp.TOTP(secret)
        code = totp.now()

        resp = await client.post("/api/v1/auth/mfa/verify", json={"code": code})
        assert resp.status_code == 200
        assert "access_token" in resp.cookies

    async def test_mfa_verify_wrong_code(self, client: AsyncClient, seed_tenant_and_owner: dict):
        await self._login(client, seed_tenant_and_owner)
        await client.post("/api/v1/auth/mfa/setup")

        resp = await client.post("/api/v1/auth/mfa/verify", json={"code": "000000"})
        assert resp.status_code == 401

    async def test_mfa_setup_requires_auth(self, client: AsyncClient):
        resp = await client.post("/api/v1/auth/mfa/setup")
        assert resp.status_code == 401

    async def test_mfa_double_setup_blocked(
        self, client: AsyncClient, seed_tenant_and_owner: dict
    ):
        await self._login(client, seed_tenant_and_owner)

        setup_resp = await client.post("/api/v1/auth/mfa/setup")
        secret = setup_resp.json()["secret"]
        totp = pyotp.TOTP(secret)
        await client.post("/api/v1/auth/mfa/verify", json={"code": totp.now()})

        re_login = await _login_request(
            client,
            seed_tenant_and_owner["email"],
            seed_tenant_and_owner["password"],
        )
        client.cookies.set("access_token", re_login.cookies["access_token"])

        resp = await client.post("/api/v1/auth/mfa/setup")
        assert resp.status_code == 400

    async def test_login_after_mfa_enabled_requires_verification(
        self, client: AsyncClient, seed_tenant_and_owner: dict
    ):
        await self._login(client, seed_tenant_and_owner)

        setup_resp = await client.post("/api/v1/auth/mfa/setup")
        secret = setup_resp.json()["secret"]
        totp = pyotp.TOTP(secret)
        await client.post("/api/v1/auth/mfa/verify", json={"code": totp.now()})

        login_resp = await _login_request(
            client,
            seed_tenant_and_owner["email"],
            seed_tenant_and_owner["password"],
        )
        assert login_resp.json()["mfa_required"] is True
