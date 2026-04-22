import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.room import Room
from app.models.shift import Shift, ShiftStatus
from app.models.user import Role, User
from app.services.errors import NotFoundError, ValidationError


class ShiftService:
    def __init__(self, db: AsyncSession):
        self._db = db

    async def create(
        self,
        *,
        tenant_id: uuid.UUID,
        model_id: uuid.UUID,
        room_id: uuid.UUID,
        start_time: datetime,
        end_time: datetime | None,
    ) -> Shift:
        await self._ensure_model_in_tenant(tenant_id=tenant_id, model_id=model_id)
        await self._ensure_room_in_tenant(tenant_id=tenant_id, room_id=room_id)

        shift = Shift(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            model_id=model_id,
            room_id=room_id,
            start_time=start_time,
            end_time=end_time,
        )
        self._db.add(shift)
        await self._db.flush()
        return shift

    async def list(
        self,
        *,
        tenant_id: uuid.UUID,
        model_id: uuid.UUID | None = None,
        room_id: uuid.UUID | None = None,
        status: ShiftStatus | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[Shift], int]:
        stmt = select(Shift).where(Shift.tenant_id == tenant_id)
        count_stmt = select(func.count()).select_from(Shift).where(Shift.tenant_id == tenant_id)

        if model_id is not None:
            stmt = stmt.where(Shift.model_id == model_id)
            count_stmt = count_stmt.where(Shift.model_id == model_id)
        if room_id is not None:
            stmt = stmt.where(Shift.room_id == room_id)
            count_stmt = count_stmt.where(Shift.room_id == room_id)
        if status is not None:
            stmt = stmt.where(Shift.status == status)
            count_stmt = count_stmt.where(Shift.status == status)
        if date_from is not None:
            stmt = stmt.where(Shift.start_time >= date_from)
            count_stmt = count_stmt.where(Shift.start_time >= date_from)
        if date_to is not None:
            stmt = stmt.where(Shift.start_time <= date_to)
            count_stmt = count_stmt.where(Shift.start_time <= date_to)

        stmt = stmt.order_by(Shift.start_time.desc()).limit(limit).offset(offset)
        items = list((await self._db.execute(stmt)).scalars().all())
        total = (await self._db.execute(count_stmt)).scalar_one()
        return items, total

    async def get(self, *, tenant_id: uuid.UUID, shift_id: uuid.UUID) -> Shift:
        return await self._get_in_tenant(tenant_id=tenant_id, shift_id=shift_id)

    async def update(
        self,
        *,
        tenant_id: uuid.UUID,
        shift_id: uuid.UUID,
        status: ShiftStatus | None,
        start_time: datetime | None,
        end_time: datetime | None,
        tokens_earned: int | None,
        usd_earned: Decimal | None,
    ) -> Shift:
        shift = await self._get_in_tenant(tenant_id=tenant_id, shift_id=shift_id)

        if status is not None:
            shift.status = status
        if start_time is not None:
            shift.start_time = start_time
        if end_time is not None:
            shift.end_time = end_time
        if tokens_earned is not None:
            shift.tokens_earned = tokens_earned
        if usd_earned is not None:
            shift.usd_earned = usd_earned

        await self._db.flush()
        return shift

    async def delete(self, *, tenant_id: uuid.UUID, shift_id: uuid.UUID) -> None:
        shift = await self._get_in_tenant(tenant_id=tenant_id, shift_id=shift_id)
        await self._db.delete(shift)
        await self._db.flush()

    async def _get_in_tenant(self, *, tenant_id: uuid.UUID, shift_id: uuid.UUID) -> Shift:
        stmt = select(Shift).where(Shift.id == shift_id, Shift.tenant_id == tenant_id)
        shift = (await self._db.execute(stmt)).scalar_one_or_none()
        if shift is None:
            raise NotFoundError("Shift not found")
        return shift

    async def _ensure_model_in_tenant(self, *, tenant_id: uuid.UUID, model_id: uuid.UUID) -> None:
        stmt = select(User).where(
            User.id == model_id,
            User.tenant_id == tenant_id,
            User.role == Role.MODEL,
            User.is_active.is_(True),
        )
        if (await self._db.execute(stmt)).scalar_one_or_none() is None:
            raise ValidationError("Target user is not an active MODEL of this tenant")

    async def _ensure_room_in_tenant(self, *, tenant_id: uuid.UUID, room_id: uuid.UUID) -> None:
        stmt = select(Room).where(
            Room.id == room_id,
            Room.tenant_id == tenant_id,
            Room.is_active.is_(True),
        )
        if (await self._db.execute(stmt)).scalar_one_or_none() is None:
            raise ValidationError("Target room does not exist or is inactive in this tenant")
