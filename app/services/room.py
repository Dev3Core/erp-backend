import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.pagination import OffsetParams, count_from, paginate_offset
from app.models.room import Platform, Room, RoomStatus
from app.services.errors import ConflictError, NotFoundError


class RoomService:
    def __init__(self, db: AsyncSession):
        self._db = db

    async def create(
        self,
        *,
        tenant_id: uuid.UUID,
        name: str,
        platform: Platform,
        url: str,
    ) -> Room:
        existing = await self._db.execute(
            select(Room).where(
                Room.tenant_id == tenant_id,
                Room.platform == platform,
                Room.url == url,
            )
        )
        if existing.scalar_one_or_none() is not None:
            raise ConflictError("Room with this URL already exists on this platform")

        room = Room(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            name=name,
            platform=platform,
            url=url,
        )
        self._db.add(room)
        await self._db.flush()
        return room

    async def list(
        self,
        *,
        tenant_id: uuid.UUID,
        params: OffsetParams,
        platform: Platform | None = None,
        status: RoomStatus | None = None,
        is_active: bool | None = None,
    ) -> tuple[list[Room], int]:
        stmt = select(Room).where(Room.tenant_id == tenant_id)
        if platform is not None:
            stmt = stmt.where(Room.platform == platform)
        if status is not None:
            stmt = stmt.where(Room.status == status)
        if is_active is not None:
            stmt = stmt.where(Room.is_active.is_(is_active))
        stmt = stmt.order_by(Room.created_at.desc(), Room.id.desc())
        return await paginate_offset(
            self._db, stmt=stmt, count_stmt=count_from(stmt), params=params
        )

    async def get(self, *, tenant_id: uuid.UUID, room_id: uuid.UUID) -> Room:
        return await self._get_in_tenant(tenant_id=tenant_id, room_id=room_id)

    async def update(
        self,
        *,
        tenant_id: uuid.UUID,
        room_id: uuid.UUID,
        name: str | None,
        url: str | None,
        status: RoomStatus | None,
        is_active: bool | None,
    ) -> Room:
        room = await self._get_in_tenant(tenant_id=tenant_id, room_id=room_id)

        if name is not None:
            room.name = name
        if url is not None:
            room.url = url
        if status is not None:
            room.status = status
        if is_active is not None:
            room.is_active = is_active

        await self._db.flush()
        return room

    async def deactivate(self, *, tenant_id: uuid.UUID, room_id: uuid.UUID) -> None:
        room = await self._get_in_tenant(tenant_id=tenant_id, room_id=room_id)
        room.is_active = False
        await self._db.flush()

    async def _get_in_tenant(self, *, tenant_id: uuid.UUID, room_id: uuid.UUID) -> Room:
        stmt = select(Room).where(Room.id == room_id, Room.tenant_id == tenant_id)
        room = (await self._db.execute(stmt)).scalar_one_or_none()
        if room is None:
            raise NotFoundError("Room not found")
        return room
