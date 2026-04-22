import pyotp
from httpx import AsyncClient
from sqlalchemy import select

from app.models.audit_log import AuditLog
from tests.conftest import TestingSession


async def _actions_for_email(email: str) -> list[str]:
    from app.models.user import User

    async with TestingSession() as session:
        user = (await session.execute(select(User).where(User.email == email))).scalar_one()
        rows = await session.execute(
            select(AuditLog).where(AuditLog.user_id == user.id).order_by(AuditLog.created_at)
        )
        return [row.action for row in rows.scalars().all()]


async def test_register_writes_audit(client: AsyncClient) -> None:
    resp = await client.post(
        "/api/v1/auth/register",
        json={
            "studio_name": "Audit Studio",
            "full_name": "Audit User",
            "email": "audit1@example.com",
            "password": "StrongPass123",
        },
    )
    assert resp.status_code == 201
    assert "auth.register" in await _actions_for_email("audit1@example.com")


async def test_login_success_writes_audit(
    client: AsyncClient, seed_tenant_and_owner: dict
) -> None:
    resp = await client.post(
        "/api/v1/auth/login",
        json={
            "email": seed_tenant_and_owner["email"],
            "password": seed_tenant_and_owner["password"],
        },
    )
    assert resp.status_code == 200
    assert "auth.login.success" in await _actions_for_email(seed_tenant_and_owner["email"])


async def test_login_failure_writes_audit_when_user_exists(
    client: AsyncClient, seed_tenant_and_owner: dict
) -> None:
    resp = await client.post(
        "/api/v1/auth/login",
        json={"email": seed_tenant_and_owner["email"], "password": "WrongPass123"},
    )
    assert resp.status_code == 401
    actions = await _actions_for_email(seed_tenant_and_owner["email"])
    assert "auth.login.failure" in actions


async def test_mfa_setup_and_verify_write_audit(
    client: AsyncClient, seed_tenant_and_owner: dict
) -> None:
    login = await client.post(
        "/api/v1/auth/login",
        json={
            "email": seed_tenant_and_owner["email"],
            "password": seed_tenant_and_owner["password"],
        },
    )
    assert login.status_code == 200

    setup = await client.post("/api/v1/auth/mfa/setup")
    assert setup.status_code == 200
    secret = setup.json()["secret"]

    verify = await client.post(
        "/api/v1/auth/mfa/verify",
        json={"code": pyotp.TOTP(secret).now()},
    )
    assert verify.status_code == 200

    actions = await _actions_for_email(seed_tenant_and_owner["email"])
    assert "auth.mfa.setup" in actions
    assert "auth.mfa.verify.success" in actions
