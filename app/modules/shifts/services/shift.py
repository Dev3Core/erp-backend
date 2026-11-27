import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.identity import Role, user_has_role_in_tenant
from app.modules.shifts.models.shift import Shift, ShiftStatus
from app.modules.shifts.services.shift_report import ShiftReportService
from app.modules.studio import room_is_active_in_tenant
from app.shared.errors import NotFoundError, ValidationError
from app.shared.pagination import CursorParams, paginate_cursor


async def get_shift_in_tenant(
    db: AsyncSession, *, tenant_id: uuid.UUID, shift_id: uuid.UUID
) -> Shift:
    """Tenant-scoped fetch; raises NotFoundError. Public: other modules read shifts via this."""
    stmt = select(Shift).where(Shift.id == shift_id, Shift.tenant_id == tenant_id)
    shift = (await db.execute(stmt)).scalar_one_or_none()
    if shift is None:
        raise NotFoundError("Shift not found")
    return shift


class ShiftService:
    def __init__(self, db: AsyncSession):
        self._db = db
        self._reports = ShiftReportService(db)

    async def create(
        self,
        *,
        tenant_id: uuid.UUID,
        model_id: uuid.UUID,
        room_id: uuid.UUID,
        start_time: datetime,
        end_time: datetime | None,
        monitor_id: uuid.UUID | None = None,
    ) -> Shift:
        await self._ensure_model_in_tenant(tenant_id=tenant_id, model_id=model_id)
        await self._ensure_room_in_tenant(tenant_id=tenant_id, room_id=room_id)
        if monitor_id is not None:
            await self._ensure_monitor_in_tenant(tenant_id=tenant_id, monitor_id=monitor_id)

        shift = Shift(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            model_id=model_id,
            room_id=room_id,
            monitor_id=monitor_id,
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
        params: CursorParams,
        model_id: uuid.UUID | None = None,
        room_id: uuid.UUID | None = None,
        monitor_id: uuid.UUID | None = None,
        status: ShiftStatus | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
    ) -> tuple[list[Shift], str | None, str | None]:
        stmt = select(Shift).where(Shift.tenant_id == tenant_id)
        if model_id is not None:
            stmt = stmt.where(Shift.model_id == model_id)
        if room_id is not None:
            stmt = stmt.where(Shift.room_id == room_id)
        if monitor_id is not None:
            stmt = stmt.where(Shift.monitor_id == monitor_id)
        if status is not None:
            stmt = stmt.where(Shift.status == status)
        if date_from is not None:
            stmt = stmt.where(Shift.start_time >= date_from)
        if date_to is not None:
            stmt = stmt.where(Shift.start_time <= date_to)

        return await paginate_cursor(
            self._db,
            stmt=stmt,
            params=params,
            created_col=Shift.created_at,
            id_col=Shift.id,
        )

    async def get(self, *, tenant_id: uuid.UUID, shift_id: uuid.UUID) -> Shift:
        return await self._get_in_tenant(tenant_id=tenant_id, shift_id=shift_id)

    async def update(
        self,
        *,
        tenant_id: uuid.UUID,
        shift_id: uuid.UUID,
        monitor_id: uuid.UUID | None,
        status: ShiftStatus | None,
        start_time: datetime | None,
        end_time: datetime | None,
        tokens_earned: int | None,
        usd_earned: Decimal | None,
    ) -> Shift:
        shift = await self._get_in_tenant(tenant_id=tenant_id, shift_id=shift_id)

        if monitor_id is not None:
            await self._ensure_monitor_in_tenant(tenant_id=tenant_id, monitor_id=monitor_id)
            shift.monitor_id = monitor_id
        will_finish = (
            status is not None
            and status == ShiftStatus.FINISHED
            and shift.status != ShiftStatus.FINISHED
        )
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
        if will_finish:
            await self._reports.generate_if_missing(tenant_id=tenant_id, shift=shift)
        return shift

    async def delete(self, *, tenant_id: uuid.UUID, shift_id: uuid.UUID) -> None:
        shift = await self._get_in_tenant(tenant_id=tenant_id, shift_id=shift_id)
        await self._db.delete(shift)
        await self._db.flush()

    async def _get_in_tenant(self, *, tenant_id: uuid.UUID, shift_id: uuid.UUID) -> Shift:
        return await get_shift_in_tenant(self._db, tenant_id=tenant_id, shift_id=shift_id)

    async def _ensure_model_in_tenant(self, *, tenant_id: uuid.UUID, model_id: uuid.UUID) -> None:
        if not await user_has_role_in_tenant(
            self._db, tenant_id=tenant_id, user_id=model_id, role=Role.MODEL, active_only=True
        ):
            raise ValidationError("Target user is not an active MODEL of this tenant")

    async def _ensure_monitor_in_tenant(
        self, *, tenant_id: uuid.UUID, monitor_id: uuid.UUID
    ) -> None:
        if not await user_has_role_in_tenant(
            self._db, tenant_id=tenant_id, user_id=monitor_id, role=Role.MONITOR, active_only=True
        ):
            raise ValidationError("Target user is not an active MONITOR of this tenant")

    async def _ensure_room_in_tenant(self, *, tenant_id: uuid.UUID, room_id: uuid.UUID) -> None:
        if not await room_is_active_in_tenant(self._db, tenant_id=tenant_id, room_id=room_id):
            raise ValidationError("Target room does not exist or is inactive in this tenant")
