"""Tests for GET /auth/me and the minimal-JWT contract."""

from httpx import AsyncClient
from jose import jwt

from app.config import settings


class TestMeEndpoint:
    async def test_requires_auth(self, client: AsyncClient):
        resp = await client.get("/api/v1/auth/me")
        assert resp.status_code == 401

    async def test_returns_session_info(self, owner_client_a: AsyncClient, tenant_a: dict):
        resp = await owner_client_a.get("/api/v1/auth/me")
        assert resp.status_code == 200
        data = resp.json()
        assert data["user_id"] == tenant_a["owner_id"]
        assert data["email"] == tenant_a["owner_email"]
        assert data["role"] == "OWNER"
        assert data["is_active"] is True
        assert data["tenant_id"] == tenant_a["tenant_id"]
        assert data["studio_slug"] == tenant_a["slug"]

    async def test_is_scoped_to_current_user_only(
        self,
        owner_client_a: AsyncClient,
        owner_client_b: AsyncClient,
        tenant_a: dict,
        tenant_b: dict,
    ):
        a = (await owner_client_a.get("/api/v1/auth/me")).json()
        b = (await owner_client_b.get("/api/v1/auth/me")).json()
        assert a["tenant_id"] == tenant_a["tenant_id"]
        assert b["tenant_id"] == tenant_b["tenant_id"]
        assert a["tenant_id"] != b["tenant_id"]


class TestMinimalJwt:
    async def test_jwt_does_not_leak_role_or_tenant(self, owner_client_a: AsyncClient):
        # owner_client_a has access_token cookie set
        token = owner_client_a.cookies.get("access_token")
        assert token is not None
        payload = jwt.decode(
            token,
            settings.JWT_SECRET.get_secret_value(),
            algorithms=[settings.JWT_ALGORITHM],
        )
        # Required claims
        assert "sub" in payload
        assert "jti" in payload
        assert "exp" in payload
        assert "type" in payload
        assert "mfa_verified" in payload
        # Must NOT be in the JWT — the front gets these from /auth/me.
        assert "role" not in payload
        assert "tenant_id" not in payload
