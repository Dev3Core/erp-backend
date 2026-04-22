import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.monitor_salary import MonitorSalary
from app.models.user import Role, User
from app.services.errors import NotFoundError, ValidationError


class MonitorSalaryService:
    """Append-only history of monitor salaries. Each row represents the salary
    effective from `effective_from` until a newer row supersedes it."""

    def __init__(self, db: AsyncSession):
        self._db = db

    async def create(
        self,
        *,
        tenant_id: uuid.UUID,
        monitor_id: uuid.UUID,
        amount_cop: Decimal,
        effective_from: date,
        notes: str | None,
    ) -> MonitorSalary:
        await self._ensure_monitor(tenant_id=tenant_id, monitor_id=monitor_id)
        entry = MonitorSalary(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            monitor_id=monitor_id,
            amount_cop=amount_cop,
            effective_from=effective_from,
            notes=notes,
        )
        self._db.add(entry)
        await self._db.flush()
        return entry

    async def list(
        self,
        *,
        tenant_id: uuid.UUID,
        monitor_id: uuid.UUID | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[MonitorSalary], int]:
        stmt = select(MonitorSalary).where(MonitorSalary.tenant_id == tenant_id)
        count_stmt = (
            select(func.count())
            .select_from(MonitorSalary)
            .where(MonitorSalary.tenant_id == tenant_id)
        )
        if monitor_id is not None:
            stmt = stmt.where(MonitorSalary.monitor_id == monitor_id)
            count_stmt = count_stmt.where(MonitorSalary.monitor_id == monitor_id)

        stmt = stmt.order_by(MonitorSalary.effective_from.desc()).limit(limit).offset(offset)
        items = list((await self._db.execute(stmt)).scalars().all())
        total = (await self._db.execute(count_stmt)).scalar_one()
        return items, total

    async def current_for(
        self, *, tenant_id: uuid.UUID, monitor_id: uuid.UUID, as_of: date
    ) -> MonitorSalary | None:
        stmt = (
            select(MonitorSalary)
            .where(
                MonitorSalary.tenant_id == tenant_id,
                MonitorSalary.monitor_id == monitor_id,
                MonitorSalary.effective_from <= as_of,
            )
            .order_by(MonitorSalary.effective_from.desc())
            .limit(1)
        )
        return (await self._db.execute(stmt)).scalar_one_or_none()

    async def get(self, *, tenant_id: uuid.UUID, salary_id: uuid.UUID) -> MonitorSalary:
        return await self._get_in_tenant(tenant_id=tenant_id, salary_id=salary_id)

    async def delete(self, *, tenant_id: uuid.UUID, salary_id: uuid.UUID) -> None:
        entry = await self._get_in_tenant(tenant_id=tenant_id, salary_id=salary_id)
        await self._db.delete(entry)
        await self._db.flush()

    async def _get_in_tenant(self, *, tenant_id: uuid.UUID, salary_id: uuid.UUID) -> MonitorSalary:
        stmt = select(MonitorSalary).where(
            MonitorSalary.id == salary_id,
            MonitorSalary.tenant_id == tenant_id,
        )
        entry = (await self._db.execute(stmt)).scalar_one_or_none()
        if entry is None:
            raise NotFoundError("Monitor salary not found")
        return entry

    async def _ensure_monitor(self, *, tenant_id: uuid.UUID, monitor_id: uuid.UUID) -> None:
        stmt = select(User).where(
            User.id == monitor_id,
            User.tenant_id == tenant_id,
            User.role == Role.MONITOR,
        )
        if (await self._db.execute(stmt)).scalar_one_or_none() is None:
            raise ValidationError("Target user is not a MONITOR of this tenant")
