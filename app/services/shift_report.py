import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.shift import Shift
from app.models.shift_report import ShiftReport
from app.services.errors import NotFoundError


class ShiftReportService:
    """Immutable end-of-shift summary. Generated when a Shift transitions to FINISHED."""

    def __init__(self, db: AsyncSession):
        self._db = db

    async def generate_if_missing(self, *, tenant_id: uuid.UUID, shift: Shift) -> ShiftReport:
        existing = await self._db.execute(
            select(ShiftReport).where(ShiftReport.shift_id == shift.id)
        )
        already = existing.scalar_one_or_none()
        if already is not None:
            return already

        duration_min = 0
        if shift.end_time is not None and shift.start_time is not None:
            delta = shift.end_time - shift.start_time
            duration_min = max(int(delta.total_seconds() // 60), 0)

        summary_lines = [
            f"duration={duration_min}min",
            f"tokens={shift.tokens_earned}",
            f"usd={shift.usd_earned}",
        ]
        report = ShiftReport(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            shift_id=shift.id,
            duration_minutes=duration_min,
            total_tokens=shift.tokens_earned,
            total_usd=shift.usd_earned,
            summary="; ".join(summary_lines),
        )
        self._db.add(report)
        await self._db.flush()
        return report

    async def list_for_tenant(
        self,
        *,
        tenant_id: uuid.UUID,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[ShiftReport], int]:
        stmt = (
            select(ShiftReport)
            .where(ShiftReport.tenant_id == tenant_id)
            .order_by(ShiftReport.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        count_stmt = (
            select(func.count()).select_from(ShiftReport).where(ShiftReport.tenant_id == tenant_id)
        )
        items = list((await self._db.execute(stmt)).scalars().all())
        total = (await self._db.execute(count_stmt)).scalar_one()
        return items, total

    async def get_for_shift(self, *, tenant_id: uuid.UUID, shift_id: uuid.UUID) -> ShiftReport:
        stmt = select(ShiftReport).where(
            ShiftReport.tenant_id == tenant_id, ShiftReport.shift_id == shift_id
        )
        report = (await self._db.execute(stmt)).scalar_one_or_none()
        if report is None:
            raise NotFoundError("Shift report not found")
        return report
