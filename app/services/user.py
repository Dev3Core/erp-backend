import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.pagination import OffsetParams, count_from, paginate_offset
from app.core.security import hash_password
from app.models.user import Role, User
from app.services.errors import ConflictError, ForbiddenError, NotFoundError, ValidationError


class UserService:
    """Tenant-scoped user management. Always receives tenant_id explicitly."""

    def __init__(self, db: AsyncSession):
        self._db = db

    async def create(
        self,
        *,
        tenant_id: uuid.UUID,
        actor: User,
        email: str,
        password: str,
        full_name: str,
        role: Role,
    ) -> User:
        self._require_admin_or_owner(actor)
        self._require_assignable_role(role, actor)

        existing = await self._db.execute(select(User).where(User.email == email))
        if existing.scalar_one_or_none() is not None:
            raise ConflictError("Email already registered")

        user = User(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            email=email,
            hashed_password=hash_password(password),
            full_name=full_name,
            role=role,
        )
        self._db.add(user)
        await self._db.flush()
        return user

    async def list(
        self,
        *,
        tenant_id: uuid.UUID,
        params: OffsetParams,
        role: Role | None = None,
        is_active: bool | None = None,
    ) -> tuple[list[User], int]:
        stmt = select(User).where(User.tenant_id == tenant_id)
        if role is not None:
            stmt = stmt.where(User.role == role)
        if is_active is not None:
            stmt = stmt.where(User.is_active.is_(is_active))
        stmt = stmt.order_by(User.created_at.desc(), User.id.desc())
        return await paginate_offset(
            self._db, stmt=stmt, count_stmt=count_from(stmt), params=params
        )

    async def get(self, *, tenant_id: uuid.UUID, user_id: uuid.UUID) -> User:
        user = await self._get_in_tenant(tenant_id=tenant_id, user_id=user_id)
        return user

    async def update(
        self,
        *,
        tenant_id: uuid.UUID,
        user_id: uuid.UUID,
        actor: User,
        full_name: str | None,
        role: Role | None,
        is_active: bool | None,
    ) -> User:
        self._require_admin_or_owner(actor)
        target = await self._get_in_tenant(tenant_id=tenant_id, user_id=user_id)

        if target.role == Role.OWNER:
            raise ForbiddenError("Owner account cannot be modified")

        if full_name is not None:
            target.full_name = full_name

        if role is not None and role != target.role:
            self._require_assignable_role(role, actor)
            target.role = role

        if is_active is not None:
            target.is_active = is_active

        await self._db.flush()
        return target

    async def deactivate(
        self,
        *,
        tenant_id: uuid.UUID,
        user_id: uuid.UUID,
        actor: User,
    ) -> None:
        self._require_admin_or_owner(actor)
        target = await self._get_in_tenant(tenant_id=tenant_id, user_id=user_id)

        if target.role == Role.OWNER:
            raise ForbiddenError("Owner account cannot be deactivated")
        if target.id == actor.id:
            raise ForbiddenError("Cannot deactivate your own account")

        target.is_active = False
        await self._db.flush()

    async def _get_in_tenant(self, *, tenant_id: uuid.UUID, user_id: uuid.UUID) -> User:
        stmt = select(User).where(User.id == user_id, User.tenant_id == tenant_id)
        user = (await self._db.execute(stmt)).scalar_one_or_none()
        if user is None:
            raise NotFoundError("User not found")
        return user

    @staticmethod
    def _require_admin_or_owner(actor: User) -> None:
        if actor.role not in (Role.OWNER, Role.ADMIN):
            raise ForbiddenError()

    @staticmethod
    def _require_assignable_role(role: Role, actor: User) -> None:
        if role == Role.OWNER:
            raise ValidationError("Cannot assign OWNER role")
        if role == Role.ADMIN and actor.role != Role.OWNER:
            raise ForbiddenError("Only OWNER can assign ADMIN role")
