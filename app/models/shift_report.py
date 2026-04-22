import uuid
from decimal import Decimal

from sqlalchemy import ForeignKey, Numeric, Text, text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TenantMixin, TimestampMixin


class ShiftReport(TenantMixin, TimestampMixin, Base):
    """Snapshot generated when a shift transitions to FINISHED. Immutable once created."""

    __tablename__ = "shift_reports"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True, server_default=text("gen_random_uuid()")
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    shift_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("shifts.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    duration_minutes: Mapped[int] = mapped_column(default=0, nullable=False)
    total_tokens: Mapped[int] = mapped_column(default=0, nullable=False)
    total_usd: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0, nullable=False)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
