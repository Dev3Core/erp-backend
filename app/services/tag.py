import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.pagination import OffsetParams, count_from, paginate_offset
from app.models.room import Platform, Room
from app.models.tag import Tag
from app.services.errors import ConflictError, NotFoundError, ValidationError


class TagService:
    def __init__(self, db: AsyncSession):
        self._db = db

    async def create(
        self,
        *,
        tenant_id: uuid.UUID,
        room_id: uuid.UUID,
        value: str,
        platform: Platform,
    ) -> Tag:
        await self._ensure_room_in_tenant(tenant_id=tenant_id, room_id=room_id)

        dup = await self._db.execute(
            select(Tag).where(
                Tag.tenant_id == tenant_id,
                Tag.room_id == room_id,
                Tag.value == value,
                Tag.platform == platform,
            )
        )
        if dup.scalar_one_or_none() is not None:
            raise ConflictError("Tag already exists on this room for this platform")

        entry = Tag(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            room_id=room_id,
            value=value,
            platform=platform,
        )
        self._db.add(entry)
        await self._db.flush()
        return entry

    async def list_for_room(
        self,
        *,
        tenant_id: uuid.UUID,
        params: OffsetParams,
        room_id: uuid.UUID | None = None,
        platform: Platform | None = None,
        active_only: bool = False,
    ) -> tuple[list[Tag], int]:
        stmt = select(Tag).where(Tag.tenant_id == tenant_id)
        if room_id is not None:
            stmt = stmt.where(Tag.room_id == room_id)
        if platform is not None:
            stmt = stmt.where(Tag.platform == platform)
        if active_only:
            stmt = stmt.where(Tag.is_active.is_(True))
        stmt = stmt.order_by(Tag.value.asc(), Tag.id.asc())
        return await paginate_offset(
            self._db, stmt=stmt, count_stmt=count_from(stmt), params=params
        )

    async def set_active(self, *, tenant_id: uuid.UUID, tag_id: uuid.UUID, is_active: bool) -> Tag:
        entry = await self._get_in_tenant(tenant_id=tenant_id, tag_id=tag_id)
        entry.is_active = is_active
        await self._db.flush()
        return entry

    async def delete(self, *, tenant_id: uuid.UUID, tag_id: uuid.UUID) -> None:
        entry = await self._get_in_tenant(tenant_id=tenant_id, tag_id=tag_id)
        await self._db.delete(entry)
        await self._db.flush()

    async def _get_in_tenant(self, *, tenant_id: uuid.UUID, tag_id: uuid.UUID) -> Tag:
        stmt = select(Tag).where(Tag.id == tag_id, Tag.tenant_id == tenant_id)
        entry = (await self._db.execute(stmt)).scalar_one_or_none()
        if entry is None:
            raise NotFoundError("Tag not found")
        return entry

    async def _ensure_room_in_tenant(self, *, tenant_id: uuid.UUID, room_id: uuid.UUID) -> None:
        stmt = select(Room).where(Room.id == room_id, Room.tenant_id == tenant_id)
        if (await self._db.execute(stmt)).scalar_one_or_none() is None:
            raise ValidationError("Target room not in this tenant")
