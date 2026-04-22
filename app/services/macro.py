import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.macro import Macro
from app.models.room import Platform
from app.services.errors import NotFoundError


class MacroService:
    def __init__(self, db: AsyncSession):
        self._db = db

    async def create(
        self,
        *,
        tenant_id: uuid.UUID,
        user_id: uuid.UUID,
        label: str,
        content: str,
        platform: Platform | None,
        position: int,
    ) -> Macro:
        entry = Macro(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            user_id=user_id,
            label=label,
            content=content,
            platform=platform,
            position=position,
        )
        self._db.add(entry)
        await self._db.flush()
        return entry

    async def list_for_user(
        self,
        *,
        tenant_id: uuid.UUID,
        user_id: uuid.UUID,
        platform: Platform | None = None,
        active_only: bool = True,
    ) -> tuple[list[Macro], int]:
        stmt = select(Macro).where(
            Macro.tenant_id == tenant_id,
            Macro.user_id == user_id,
        )
        count_stmt = (
            select(func.count())
            .select_from(Macro)
            .where(Macro.tenant_id == tenant_id, Macro.user_id == user_id)
        )
        if platform is not None:
            stmt = stmt.where(Macro.platform == platform)
            count_stmt = count_stmt.where(Macro.platform == platform)
        if active_only:
            stmt = stmt.where(Macro.is_active.is_(True))
            count_stmt = count_stmt.where(Macro.is_active.is_(True))
        stmt = stmt.order_by(Macro.position.asc(), Macro.created_at.asc())
        items = list((await self._db.execute(stmt)).scalars().all())
        total = (await self._db.execute(count_stmt)).scalar_one()
        return items, total

    async def update(
        self,
        *,
        tenant_id: uuid.UUID,
        user_id: uuid.UUID,
        macro_id: uuid.UUID,
        label: str | None,
        content: str | None,
        platform: Platform | None,
        position: int | None,
        is_active: bool | None,
    ) -> Macro:
        entry = await self._get_in_scope(tenant_id=tenant_id, user_id=user_id, macro_id=macro_id)
        if label is not None:
            entry.label = label
        if content is not None:
            entry.content = content
        if platform is not None:
            entry.platform = platform
        if position is not None:
            entry.position = position
        if is_active is not None:
            entry.is_active = is_active
        await self._db.flush()
        return entry

    async def delete(
        self, *, tenant_id: uuid.UUID, user_id: uuid.UUID, macro_id: uuid.UUID
    ) -> None:
        entry = await self._get_in_scope(tenant_id=tenant_id, user_id=user_id, macro_id=macro_id)
        await self._db.delete(entry)
        await self._db.flush()

    async def _get_in_scope(
        self, *, tenant_id: uuid.UUID, user_id: uuid.UUID, macro_id: uuid.UUID
    ) -> Macro:
        stmt = select(Macro).where(
            Macro.id == macro_id,
            Macro.tenant_id == tenant_id,
            Macro.user_id == user_id,
        )
        entry = (await self._db.execute(stmt)).scalar_one_or_none()
        if entry is None:
            raise NotFoundError("Macro not found")
        return entry
