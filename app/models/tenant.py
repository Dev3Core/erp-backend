import enum
import uuid

from sqlalchemy import ForeignKey, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class Plan(str, enum.Enum):
    TRIAL = "TRIAL"
    BASIC = "BASIC"
    PRO = "PRO"
    ENTERPRISE = "ENTERPRISE"


class Tenant(TimestampMixin, Base):
    __tablename__ = "tenants"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    plan: Mapped[Plan] = mapped_column(default=Plan.TRIAL, nullable=False)
    logo_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)
    owner_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    owner: Mapped["User | None"] = relationship(  # noqa: F821
        foreign_keys=[owner_id],
    )
    users: Mapped[list["User"]] = relationship(  # noqa: F821
        back_populates="tenant", foreign_keys="User.tenant_id"
    )
    rooms: Mapped[list["Room"]] = relationship(back_populates="tenant")  # noqa: F821
