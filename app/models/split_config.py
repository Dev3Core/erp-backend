import uuid

from sqlalchemy import ForeignKey, Numeric, String, text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TenantMixin, TimestampMixin


class SplitConfig(TenantMixin, TimestampMixin, Base):
    __tablename__ = "split_configs"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    label: Mapped[str] = mapped_column(String(255), nullable=False)
    platform_pct: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False)
    studio_pct: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False)
    model_pct: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False)
    is_default: Mapped[bool] = mapped_column(default=False, nullable=False)
