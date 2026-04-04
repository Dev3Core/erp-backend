import enum
import uuid
from datetime import date

from sqlalchemy import Date, ForeignKey, Numeric, Text, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TenantMixin, TimestampMixin


class LiquidationStatus(str, enum.Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    PAID = "PAID"


class Liquidation(TenantMixin, TimestampMixin, Base):
    __tablename__ = "liquidations"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    shift_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("shifts.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )
    period_date: Mapped[date] = mapped_column(Date, nullable=False)
    gross_usd: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    net_usd: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    cop_amount: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False)
    trm_used: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    status: Mapped[LiquidationStatus] = mapped_column(
        default=LiquidationStatus.PENDING,
        nullable=False,
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    shift: Mapped["Shift"] = relationship(back_populates="liquidation")  # noqa: F821
