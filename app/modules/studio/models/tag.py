import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, text
from sqlalchemy.orm import Mapped, mapped_column

from app.modules.studio.models.room import Platform
from app.shared.orm import Base, TenantMixin, TimestampMixin


class Tag(TenantMixin, TimestampMixin, Base):
    """A tag applied (or pending) on a Room. The scraper later syncs these
    with the real platform; until then it's a tenant-managed catalog."""

    __tablename__ = "tags"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True, server_default=text("gen_random_uuid()")
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    room_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("rooms.id", ondelete="CASCADE"), nullable=False, index=True
    )
    value: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    platform: Mapped[Platform] = mapped_column(nullable=False)
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)
    last_applied_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
