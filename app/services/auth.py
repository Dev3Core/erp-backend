import logging
import re
import uuid
from datetime import UTC, datetime

import pyotp
from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.config import settings
from app.core.security import (
    TokenType,
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    token_blacklist_key,
    verify_password,
)
from app.models.audit_log import AuditLog
from app.models.tenant import Tenant
from app.models.user import Role, User

logger = logging.getLogger(__name__)


class AuthError(Exception):
    def __init__(self, detail: str, status_code: int = 401):
        self.detail = detail
        self.status_code = status_code


def _slugify(name: str) -> str:
    slug = name.lower().strip()
    slug = re.sub(r"[^\w\s-]", "", slug)
    return re.sub(r"[\s_-]+", "-", slug).strip("-")


class AuthService:
    def __init__(
        self,
        db: AsyncSession,
        redis: Redis,
        audit_session_factory: async_sessionmaker[AsyncSession] | None = None,
    ):
        self._db = db
        self._redis = redis
        self._audit_session_factory = audit_session_factory

    async def register(
        self, studio_name: str, full_name: str, email: str, password: str
    ) -> tuple[Tenant, User]:
        existing = await self._db.execute(select(User).where(User.email == email))
        if existing.scalar_one_or_none() is not None:
            raise AuthError("Email already registered", status_code=409)

        base_slug = _slugify(studio_name)
        slug = await self._ensure_unique_slug(base_slug)

        tenant = Tenant(id=uuid.uuid4(), name=studio_name, slug=slug)
        self._db.add(tenant)
        await self._db.flush()

        owner = User(
            id=uuid.uuid4(),
            tenant_id=tenant.id,
            email=email,
            hashed_password=hash_password(password),
            full_name=full_name,
            role=Role.OWNER,
        )
        self._db.add(owner)
        await self._db.flush()

        from sqlalchemy import update

        await self._db.execute(
            update(Tenant).where(Tenant.id == tenant.id).values(owner_id=owner.id)
        )
        tenant.owner_id = owner.id

        await self._audit(user=owner, action="auth.register")
        return tenant, owner

    async def authenticate(self, email: str, password: str) -> User:
        stmt = select(User).where(User.email == email, User.is_active.is_(True))
        result = await self._db.execute(stmt)
        user = result.scalar_one_or_none()

        if user is None:
            logger.info("login failed: unknown email")
            raise AuthError("Invalid credentials")

        if not verify_password(password, user.hashed_password):
            await self._audit(user=user, action="auth.login.failure")
            raise AuthError("Invalid credentials")

        tenant = await self._db.get(Tenant, user.tenant_id)
        if tenant is None or not tenant.is_active:
            await self._audit(user=user, action="auth.login.blocked")
            raise AuthError("Account suspended. Contact support.")

        await self._audit(user=user, action="auth.login.success")
        return user

    def create_token_pair(self, user: User, *, mfa_verified: bool = False) -> tuple[str, str]:
        # Minimal payload: identity + session flags only. Role and tenant are NOT in
        # the JWT — callers fetch them via GET /auth/me and the backend always reads
        # them from the DB-loaded User in request deps.
        jti = uuid.uuid4().hex
        payload = {
            "sub": str(user.id),
            "mfa_verified": mfa_verified,
            "jti": jti,
        }
        return create_access_token(payload), create_refresh_token(payload)

    async def get_session_info(self, user: User) -> tuple[User, Tenant]:
        tenant = await self._db.get(Tenant, user.tenant_id)
        if tenant is None:
            raise AuthError("Tenant not found", status_code=404)
        return user, tenant

    async def refresh_tokens(self, refresh_token: str) -> tuple[str, str, dict]:
        payload = decode_token(refresh_token)

        if payload.get("type") != TokenType.REFRESH:
            raise AuthError("Invalid token type")

        jti = payload.get("jti", "")
        if await self._is_blacklisted(str(jti)):
            raise AuthError("Token revoked")

        await self._blacklist_token(str(jti), settings.JWT_REFRESH_EXPIRES_MINUTES * 60)

        stmt = select(User).where(
            User.id == uuid.UUID(str(payload["sub"])), User.is_active.is_(True)
        )
        result = await self._db.execute(stmt)
        user = result.scalar_one_or_none()

        if user is None:
            raise AuthError("User not found")

        mfa_verified = bool(payload.get("mfa_verified", False))
        access, refresh = self.create_token_pair(user, mfa_verified=mfa_verified)
        return access, refresh, payload

    async def logout(self, access_token: str, refresh_token: str | None) -> None:
        audited = False
        for token in (access_token, refresh_token):
            if token is None:
                continue
            try:
                payload = decode_token(token)
                jti = str(payload.get("jti", ""))
                exp = int(payload.get("exp", 0))
                ttl = max(exp - int(datetime.now(UTC).timestamp()), 0)
                if jti and ttl > 0:
                    await self._blacklist_token(jti, ttl)
                if not audited:
                    user = await self._db.get(User, uuid.UUID(str(payload["sub"])))
                    if user is not None:
                        await self._audit(user=user, action="auth.logout")
                        audited = True
            except Exception:
                logger.warning("logout token blacklist failed", exc_info=True)
                continue

    async def setup_mfa(self, user: User) -> tuple[str, str]:
        if user.mfa_enabled:
            raise AuthError("MFA already enabled", status_code=400)

        secret = pyotp.random_base32()
        user.mfa_secret = secret
        await self._db.flush()

        totp = pyotp.TOTP(secret)
        uri = totp.provisioning_uri(name=user.email, issuer_name=settings.APP_NAME)
        await self._audit(user=user, action="auth.mfa.setup")
        return uri, secret

    async def verify_mfa(self, user: User, code: str) -> None:
        if user.mfa_secret is None:
            raise AuthError("MFA not configured. Call setup first.", status_code=400)

        totp = pyotp.TOTP(user.mfa_secret)
        if not totp.verify(code, valid_window=1):
            await self._audit(user=user, action="auth.mfa.verify.failure")
            raise AuthError("Invalid MFA code")

        if not user.mfa_enabled:
            user.mfa_enabled = True
            await self._db.flush()

        await self._audit(user=user, action="auth.mfa.verify.success")

    async def is_token_blacklisted(self, jti: str) -> bool:
        return await self._is_blacklisted(jti)

    async def _audit(
        self,
        *,
        user: User,
        action: str,
        details: str | None = None,
    ) -> None:
        """Best-effort audit write in an independent session to survive outer rollback."""
        try:
            entry_kwargs = {
                "id": uuid.uuid4(),
                "tenant_id": user.tenant_id,
                "user_id": user.id,
                "action": action,
                "entity_type": "user",
                "entity_id": user.id,
                "details": details,
            }
            if self._audit_session_factory is not None:
                async with self._audit_session_factory() as session:
                    session.add(AuditLog(**entry_kwargs))
                    await session.commit()
            else:
                self._db.add(AuditLog(**entry_kwargs))
                await self._db.flush()
        except Exception:
            logger.warning("audit log write failed action=%s", action, exc_info=True)

    async def _ensure_unique_slug(self, base_slug: str) -> str:
        slug = base_slug
        counter = 0
        while True:
            exists = await self._db.execute(select(Tenant).where(Tenant.slug == slug))
            if exists.scalar_one_or_none() is None:
                return slug
            counter += 1
            slug = f"{base_slug}-{counter}"

    async def _blacklist_token(self, jti: str, ttl_seconds: int) -> None:
        await self._redis.setex(token_blacklist_key(jti), ttl_seconds, "1")

    async def _is_blacklisted(self, jti: str) -> bool:
        return await self._redis.exists(token_blacklist_key(jti)) > 0
