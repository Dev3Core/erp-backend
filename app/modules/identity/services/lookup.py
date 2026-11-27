"""Read-only lookups that other modules need about users and tenants.

Exposed through `app.modules.identity` so callers validate references
(e.g. "is this user an active MODEL of the tenant?") without querying
identity's tables themselves.
"""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.identity.models.tenant import Tenant
from app.modules.identity.models.user import Role, User


async def user_has_role_in_tenant(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    user_id: uuid.UUID,
    role: Role,
    active_only: bool = False,
) -> bool:
    stmt = select(User).where(
        User.id == user_id,
        User.tenant_id == tenant_id,
        User.role == role,
    )
    if active_only:
        stmt = stmt.where(User.is_active.is_(True))
    return (await db.execute(stmt)).scalar_one_or_none() is not None


async def get_tenant_name(db: AsyncSession, tenant_id: uuid.UUID) -> str | None:
    tenant = await db.get(Tenant, tenant_id)
    return tenant.name if tenant else None
