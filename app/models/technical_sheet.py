import uuid

from sqlalchemy import ForeignKey, Text, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TenantMixin, TimestampMixin


class TechnicalSheet(TenantMixin, TimestampMixin, Base):
    __tablename__ = "technical_sheets"

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
    bio: Mapped[str | None] = mapped_column(Text, nullable=True)
    languages: Mapped[str | None] = mapped_column(Text, nullable=True)
    categories: Mapped[str | None] = mapped_column(Text, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    model: Mapped["User"] = relationship(back_populates="technical_sheets")  # noqa: F821
