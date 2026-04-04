import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Numeric, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TenantMixin, TimestampMixin


class ShiftStatus(str, enum.Enum):
    SCHEDULED = "SCHEDULED"
    ACTIVE = "ACTIVE"
    FINISHED = "FINISHED"
    CANCELLED = "CANCELLED"


class Shift(TenantMixin, TimestampMixin, Base):
    __tablename__ = "shifts"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    model_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    room_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("rooms.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    status: Mapped[ShiftStatus] = mapped_column(default=ShiftStatus.SCHEDULED, nullable=False)
    start_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    end_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    tokens_earned: Mapped[int] = mapped_column(default=0, nullable=False)
    usd_earned: Mapped[float] = mapped_column(Numeric(12, 2), default=0, nullable=False)

    model: Mapped["User"] = relationship(back_populates="shifts")  # noqa: F821
    room: Mapped["Room"] = relationship(back_populates="shifts")  # noqa: F821
    liquidation: Mapped["Liquidation | None"] = relationship(  # noqa: F821
        back_populates="shift"
    )
