import secrets
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password, verify_password
from app.models.api_key import ApiKey
from app.models.user import User
from app.services.errors import ForbiddenError, NotFoundError

_PREFIX_LEN = 12  # chars of the plaintext key shown in listings


def _generate_key() -> tuple[str, str]:
    """Return (plaintext, prefix). Plaintext is URL-safe, 48 bytes of entropy."""
    plaintext = secrets.token_urlsafe(48)
    return plaintext, plaintext[:_PREFIX_LEN]


class ApiKeyService:
    """Issues short-lived API keys tied to a user. Plaintext is only returned at
    creation; storage is argon2-hashed."""

    def __init__(self, db: AsyncSession):
        self._db = db

    async def issue(
        self,
        *,
        tenant_id: uuid.UUID,
        user: User,
        name: str | None,
        ttl_hours: int,
    ) -> tuple[ApiKey, str]:
        plaintext, prefix = _generate_key()
        now = datetime.now(UTC)
        entry = ApiKey(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            user_id=user.id,
            name=name,
            prefix=prefix,
            key_hash=hash_password(plaintext),
            expires_at=now + timedelta(hours=ttl_hours),
        )
        self._db.add(entry)
        await self._db.flush()
        return entry, plaintext

    async def list_for_user(
        self,
        *,
        tenant_id: uuid.UUID,
        user_id: uuid.UUID,
        include_revoked: bool = False,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[ApiKey], int]:
        stmt = select(ApiKey).where(
            ApiKey.tenant_id == tenant_id,
            ApiKey.user_id == user_id,
        )
        count_stmt = (
            select(func.count())
            .select_from(ApiKey)
            .where(ApiKey.tenant_id == tenant_id, ApiKey.user_id == user_id)
        )
        if not include_revoked:
            stmt = stmt.where(ApiKey.revoked_at.is_(None))
            count_stmt = count_stmt.where(ApiKey.revoked_at.is_(None))

        stmt = stmt.order_by(ApiKey.created_at.desc()).limit(limit).offset(offset)
        items = list((await self._db.execute(stmt)).scalars().all())
        total = (await self._db.execute(count_stmt)).scalar_one()
        return items, total

    async def revoke(
        self,
        *,
        tenant_id: uuid.UUID,
        key_id: uuid.UUID,
        acting_user_id: uuid.UUID,
    ) -> None:
        entry = await self._get_in_tenant(tenant_id=tenant_id, key_id=key_id)
        if entry.user_id != acting_user_id:
            raise ForbiddenError("Cannot revoke API keys that belong to another user")
        if entry.revoked_at is None:
            entry.revoked_at = datetime.now(UTC)
            await self._db.flush()

    async def verify_plaintext(self, *, plaintext: str) -> ApiKey | None:
        """Lookup an active, non-expired, non-revoked key matching the plaintext.

        Uses the prefix as a B-tree index probe, then argon2 verify on candidates.
        Prefix collisions are rare (>= 48 bytes of entropy) so the candidate set is tiny.
        """
        if len(plaintext) < _PREFIX_LEN:
            return None
        prefix = plaintext[:_PREFIX_LEN]
        now = datetime.now(UTC)
        stmt = select(ApiKey).where(
            ApiKey.prefix == prefix,
            ApiKey.revoked_at.is_(None),
            ApiKey.expires_at > now,
        )
        for candidate in (await self._db.execute(stmt)).scalars().all():
            if verify_password(plaintext, candidate.key_hash):
                candidate.last_used_at = now
                await self._db.flush()
                return candidate
        return None

    async def _get_in_tenant(self, *, tenant_id: uuid.UUID, key_id: uuid.UUID) -> ApiKey:
        stmt = select(ApiKey).where(
            ApiKey.id == key_id,
            ApiKey.tenant_id == tenant_id,
        )
        entry = (await self._db.execute(stmt)).scalar_one_or_none()
        if entry is None:
            raise NotFoundError("API key not found")
        return entry
