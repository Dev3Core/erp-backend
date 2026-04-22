import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.liquidation import Liquidation, LiquidationStatus
from app.models.room import Room
from app.models.shift import Shift, ShiftStatus
from app.models.user import User


class MetricsService:
    """Read-only aggregates for dashboards. All queries are tenant-scoped."""

    def __init__(self, db: AsyncSession):
        self._db = db

    async def overview(
        self,
        *,
        tenant_id: uuid.UUID,
        date_from: date | None,
        date_to: date | None,
    ) -> dict:
        shift_filters = [
            Shift.tenant_id == tenant_id,
            Shift.status == ShiftStatus.FINISHED,
        ]
        if date_from is not None:
            shift_filters.append(Shift.start_time >= date_from)
        if date_to is not None:
            shift_filters.append(Shift.start_time <= date_to)

        shift_stmt = select(
            func.count(Shift.id),
            func.coalesce(func.sum(Shift.tokens_earned), 0),
            func.coalesce(func.sum(Shift.usd_earned), Decimal("0")),
        ).where(and_(*shift_filters))
        total_shifts, total_tokens, total_usd = (await self._db.execute(shift_stmt)).one()

        liq_filters = [Liquidation.tenant_id == tenant_id]
        if date_from is not None:
            liq_filters.append(Liquidation.period_date >= date_from)
        if date_to is not None:
            liq_filters.append(Liquidation.period_date <= date_to)

        paid_sum_stmt = select(
            func.coalesce(func.sum(Liquidation.cop_amount), Decimal("0"))
        ).where(and_(*liq_filters, Liquidation.status == LiquidationStatus.PAID))
        total_cop_paid = (await self._db.execute(paid_sum_stmt)).scalar_one()

        by_status_stmt = (
            select(Liquidation.status, func.count(Liquidation.id))
            .where(and_(*liq_filters))
            .group_by(Liquidation.status)
        )
        counts = dict((await self._db.execute(by_status_stmt)).all())

        return {
            "period_from": date_from,
            "period_to": date_to,
            "total_shifts": int(total_shifts),
            "total_tokens": int(total_tokens),
            "total_usd": total_usd,
            "total_cop_paid": total_cop_paid,
            "liquidations_pending": int(counts.get(LiquidationStatus.PENDING, 0)),
            "liquidations_approved": int(counts.get(LiquidationStatus.APPROVED, 0)),
            "liquidations_paid": int(counts.get(LiquidationStatus.PAID, 0)),
        }

    async def revenue_by_model(
        self,
        *,
        tenant_id: uuid.UUID,
        date_from: date | None,
        date_to: date | None,
        limit: int,
    ) -> list[dict]:
        filters = [
            Shift.tenant_id == tenant_id,
            Shift.status == ShiftStatus.FINISHED,
        ]
        if date_from is not None:
            filters.append(Shift.start_time >= date_from)
        if date_to is not None:
            filters.append(Shift.start_time <= date_to)

        stmt = (
            select(
                User.id,
                User.email,
                User.full_name,
                func.count(Shift.id).label("total_shifts"),
                func.coalesce(func.sum(Shift.tokens_earned), 0).label("total_tokens"),
                func.coalesce(func.sum(Shift.usd_earned), Decimal("0")).label("total_usd"),
            )
            .join(Shift, Shift.model_id == User.id)
            .where(and_(*filters))
            .group_by(User.id, User.email, User.full_name)
            .order_by(func.sum(Shift.usd_earned).desc())
            .limit(limit)
        )
        rows = (await self._db.execute(stmt)).all()
        return [
            {
                "model_id": r.id,
                "email": r.email,
                "full_name": r.full_name,
                "total_shifts": int(r.total_shifts),
                "total_tokens": int(r.total_tokens),
                "total_usd": r.total_usd,
            }
            for r in rows
        ]

    async def revenue_by_monitor(
        self,
        *,
        tenant_id: uuid.UUID,
        date_from: date | None,
        date_to: date | None,
        limit: int,
    ) -> list[dict]:
        filters = [
            Shift.tenant_id == tenant_id,
            Shift.status == ShiftStatus.FINISHED,
        ]
        if date_from is not None:
            filters.append(Shift.start_time >= date_from)
        if date_to is not None:
            filters.append(Shift.start_time <= date_to)

        stmt = (
            select(
                User.id,
                User.email,
                User.full_name,
                func.count(Shift.id).label("total_shifts"),
                func.coalesce(func.sum(Shift.tokens_earned), 0).label("total_tokens"),
                func.coalesce(func.sum(Shift.usd_earned), Decimal("0")).label("total_usd"),
            )
            .join(Shift, Shift.monitor_id == User.id, isouter=False)
            .where(and_(*filters))
            .group_by(User.id, User.email, User.full_name)
            .order_by(func.sum(Shift.usd_earned).desc())
            .limit(limit)
        )
        rows = (await self._db.execute(stmt)).all()
        return [
            {
                "monitor_id": r.id,
                "email": r.email,
                "full_name": r.full_name,
                "total_shifts": int(r.total_shifts),
                "total_tokens": int(r.total_tokens),
                "total_usd": r.total_usd,
            }
            for r in rows
        ]

    async def revenue_by_platform(
        self,
        *,
        tenant_id: uuid.UUID,
        date_from: date | None,
        date_to: date | None,
    ) -> list[dict]:
        filters = [
            Shift.tenant_id == tenant_id,
            Shift.status == ShiftStatus.FINISHED,
        ]
        if date_from is not None:
            filters.append(Shift.start_time >= date_from)
        if date_to is not None:
            filters.append(Shift.start_time <= date_to)

        stmt = (
            select(
                Room.platform.label("platform"),
                func.count(Shift.id).label("total_shifts"),
                func.coalesce(func.sum(Shift.tokens_earned), 0).label("total_tokens"),
                func.coalesce(func.sum(Shift.usd_earned), Decimal("0")).label("total_usd"),
            )
            .join(Room, Shift.room_id == Room.id)
            .where(and_(*filters))
            .group_by(Room.platform)
            .order_by(func.sum(Shift.usd_earned).desc())
        )
        rows = (await self._db.execute(stmt)).all()
        return [
            {
                "platform": r.platform.value if hasattr(r.platform, "value") else str(r.platform),
                "total_shifts": int(r.total_shifts),
                "total_tokens": int(r.total_tokens),
                "total_usd": r.total_usd,
            }
            for r in rows
        ]

    async def daily_revenue(
        self,
        *,
        tenant_id: uuid.UUID,
        date_from: date,
        date_to: date,
        model_id: uuid.UUID | None = None,
    ) -> list[dict]:
        filters = [
            Shift.tenant_id == tenant_id,
            Shift.status == ShiftStatus.FINISHED,
            Shift.start_time >= date_from,
            Shift.start_time <= date_to,
        ]
        if model_id is not None:
            filters.append(Shift.model_id == model_id)

        day_col = func.date(Shift.start_time).label("day")
        stmt = (
            select(
                day_col,
                func.count(Shift.id).label("total_shifts"),
                func.coalesce(func.sum(Shift.tokens_earned), 0).label("total_tokens"),
                func.coalesce(func.sum(Shift.usd_earned), Decimal("0")).label("total_usd"),
            )
            .where(and_(*filters))
            .group_by(day_col)
            .order_by(day_col.asc())
        )
        rows = (await self._db.execute(stmt)).all()
        return [
            {
                "day": r.day,
                "total_shifts": int(r.total_shifts),
                "total_tokens": int(r.total_tokens),
                "total_usd": r.total_usd,
            }
            for r in rows
        ]

    async def model_overview(
        self,
        *,
        tenant_id: uuid.UUID,
        model_id: uuid.UUID,
        date_from: date | None,
        date_to: date | None,
    ) -> dict:
        filters = [
            Shift.tenant_id == tenant_id,
            Shift.model_id == model_id,
            Shift.status == ShiftStatus.FINISHED,
        ]
        if date_from is not None:
            filters.append(Shift.start_time >= date_from)
        if date_to is not None:
            filters.append(Shift.start_time <= date_to)

        stmt = select(
            func.count(Shift.id),
            func.coalesce(func.sum(Shift.tokens_earned), 0),
            func.coalesce(func.sum(Shift.usd_earned), Decimal("0")),
        ).where(and_(*filters))
        total_shifts, total_tokens, total_usd = (await self._db.execute(stmt)).one()

        return {
            "model_id": model_id,
            "period_from": date_from,
            "period_to": date_to,
            "total_shifts": int(total_shifts),
            "total_tokens": int(total_tokens),
            "total_usd": total_usd,
        }

    async def best_monitor_for_model(
        self,
        *,
        tenant_id: uuid.UUID,
        model_id: uuid.UUID,
    ) -> dict | None:
        filters = [
            Shift.tenant_id == tenant_id,
            Shift.model_id == model_id,
            Shift.status == ShiftStatus.FINISHED,
            Shift.monitor_id.isnot(None),
        ]
        stmt = (
            select(
                User.id,
                User.full_name,
                func.count(Shift.id).label("total_shifts"),
                func.coalesce(func.sum(Shift.usd_earned), Decimal("0")).label("total_usd"),
            )
            .join(Shift, Shift.monitor_id == User.id)
            .where(and_(*filters))
            .group_by(User.id, User.full_name)
            .order_by(func.sum(Shift.usd_earned).desc())
            .limit(1)
        )
        row = (await self._db.execute(stmt)).first()
        if row is None:
            return None
        return {
            "monitor_id": row.id,
            "full_name": row.full_name,
            "total_shifts": int(row.total_shifts),
            "total_usd": row.total_usd,
        }
