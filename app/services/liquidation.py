from __future__ import annotations

import uuid
from datetime import UTC, date, datetime
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.pagination import CursorParams, paginate_cursor
from app.models.liquidation import Liquidation, LiquidationStatus
from app.models.shift import Shift
from app.models.split_config import SplitConfig
from app.services.errors import ConflictError, NotFoundError, ValidationError
from app.services.exchange_rate import ExchangeRateService


def _to_money(d: Decimal) -> Decimal:
    return d.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


class LiquidationService:
    """Creates liquidations from finished shifts. Applies a split to compute model net,
    then converts USD to COP using the TRM for the period date (cache-aside)."""

    def __init__(self, db: AsyncSession, exchange_rates: ExchangeRateService):
        self._db = db
        self._exchange_rates = exchange_rates

    async def create_from_shift(
        self,
        *,
        tenant_id: uuid.UUID,
        shift_id: uuid.UUID,
        split_config_id: uuid.UUID | None,
        period_date: date | None,
        notes: str | None,
    ) -> Liquidation:
        shift = await self._get_shift(tenant_id=tenant_id, shift_id=shift_id)
        if shift.status != "FINISHED" and shift.status.value != "FINISHED":
            raise ValidationError("Shift must be FINISHED before liquidation")

        existing = await self._db.execute(
            select(Liquidation).where(Liquidation.shift_id == shift_id)
        )
        if existing.scalar_one_or_none() is not None:
            raise ConflictError("Liquidation already exists for this shift")

        split = await self._pick_split(tenant_id=tenant_id, split_config_id=split_config_id)
        target_date = period_date or datetime.now(UTC).date()

        rate = await self._exchange_rates.get_for_date(target_date)

        gross_usd = Decimal(str(shift.usd_earned))
        # Platform cut is excluded from studio revenue; studio + model shares split the rest.
        post_platform = (
            gross_usd * (Decimal("100") - Decimal(str(split.platform_pct))) / Decimal("100")
        )
        model_pct_of_post = Decimal(str(split.model_pct)) / (
            Decimal(str(split.studio_pct)) + Decimal(str(split.model_pct))
        )
        net_usd = _to_money(post_platform * model_pct_of_post)
        cop_amount = _to_money(net_usd * Decimal(str(rate.cop_per_usd)))

        liq = Liquidation(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            shift_id=shift_id,
            period_date=target_date,
            gross_usd=_to_money(gross_usd),
            net_usd=net_usd,
            cop_amount=cop_amount,
            trm_used=Decimal(str(rate.cop_per_usd)),
            status=LiquidationStatus.PENDING,
            notes=notes,
        )
        self._db.add(liq)
        await self._db.flush()
        return liq

    async def list(
        self,
        *,
        tenant_id: uuid.UUID,
        params: CursorParams,
        status: LiquidationStatus | None = None,
        date_from: date | None = None,
        date_to: date | None = None,
        shift_id: uuid.UUID | None = None,
    ) -> tuple[list[Liquidation], str | None, str | None]:
        stmt = select(Liquidation).where(Liquidation.tenant_id == tenant_id)
        if status is not None:
            stmt = stmt.where(Liquidation.status == status)
        if date_from is not None:
            stmt = stmt.where(Liquidation.period_date >= date_from)
        if date_to is not None:
            stmt = stmt.where(Liquidation.period_date <= date_to)
        if shift_id is not None:
            stmt = stmt.where(Liquidation.shift_id == shift_id)
        return await paginate_cursor(
            self._db,
            stmt=stmt,
            params=params,
            created_col=Liquidation.created_at,
            id_col=Liquidation.id,
        )

    async def list_all_for_export(
        self,
        *,
        tenant_id: uuid.UUID,
        status: LiquidationStatus | None = None,
        date_from: date | None = None,
        date_to: date | None = None,
        max_rows: int = 10000,
    ) -> list[Liquidation]:
        """Non-paginated read for exports. Hard-capped at `max_rows` to keep memory bounded."""
        stmt = select(Liquidation).where(Liquidation.tenant_id == tenant_id)
        if status is not None:
            stmt = stmt.where(Liquidation.status == status)
        if date_from is not None:
            stmt = stmt.where(Liquidation.period_date >= date_from)
        if date_to is not None:
            stmt = stmt.where(Liquidation.period_date <= date_to)
        stmt = stmt.order_by(Liquidation.period_date.desc(), Liquidation.id.desc()).limit(max_rows)
        return list((await self._db.execute(stmt)).scalars().all())

    async def get(self, *, tenant_id: uuid.UUID, liquidation_id: uuid.UUID) -> Liquidation:
        return await self._get_in_tenant(tenant_id=tenant_id, liquidation_id=liquidation_id)

    async def transition_status(
        self,
        *,
        tenant_id: uuid.UUID,
        liquidation_id: uuid.UUID,
        new_status: LiquidationStatus,
        notes: str | None,
    ) -> Liquidation:
        liq = await self._get_in_tenant(tenant_id=tenant_id, liquidation_id=liquidation_id)
        self._validate_transition(liq.status, new_status)
        liq.status = new_status
        if notes is not None:
            liq.notes = notes
        await self._db.flush()
        return liq

    async def delete(self, *, tenant_id: uuid.UUID, liquidation_id: uuid.UUID) -> None:
        liq = await self._get_in_tenant(tenant_id=tenant_id, liquidation_id=liquidation_id)
        if liq.status == LiquidationStatus.PAID:
            raise ValidationError("Cannot delete a PAID liquidation")
        await self._db.delete(liq)
        await self._db.flush()

    async def _get_shift(self, *, tenant_id: uuid.UUID, shift_id: uuid.UUID) -> Shift:
        stmt = select(Shift).where(Shift.id == shift_id, Shift.tenant_id == tenant_id)
        shift = (await self._db.execute(stmt)).scalar_one_or_none()
        if shift is None:
            raise NotFoundError("Shift not found")
        return shift

    async def _pick_split(
        self, *, tenant_id: uuid.UUID, split_config_id: uuid.UUID | None
    ) -> SplitConfig:
        if split_config_id is not None:
            stmt = select(SplitConfig).where(
                SplitConfig.id == split_config_id,
                SplitConfig.tenant_id == tenant_id,
            )
            split = (await self._db.execute(stmt)).scalar_one_or_none()
            if split is None:
                raise NotFoundError("Split config not found")
            return split

        stmt = select(SplitConfig).where(
            SplitConfig.tenant_id == tenant_id,
            SplitConfig.is_default.is_(True),
        )
        split = (await self._db.execute(stmt)).scalar_one_or_none()
        if split is None:
            raise ValidationError(
                "No default split configured for this tenant; pass split_config_id explicitly."
            )
        return split

    async def _get_in_tenant(
        self, *, tenant_id: uuid.UUID, liquidation_id: uuid.UUID
    ) -> Liquidation:
        stmt = select(Liquidation).where(
            Liquidation.id == liquidation_id,
            Liquidation.tenant_id == tenant_id,
        )
        liq = (await self._db.execute(stmt)).scalar_one_or_none()
        if liq is None:
            raise NotFoundError("Liquidation not found")
        return liq

    @staticmethod
    def _validate_transition(current: LiquidationStatus, new: LiquidationStatus) -> None:
        allowed = {
            LiquidationStatus.PENDING: {LiquidationStatus.APPROVED},
            LiquidationStatus.APPROVED: {LiquidationStatus.PAID, LiquidationStatus.PENDING},
            LiquidationStatus.PAID: set(),
        }
        if new not in allowed.get(current, set()):
            raise ValidationError(f"Invalid status transition {current.value} -> {new.value}")
