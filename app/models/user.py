import enum
import uuid

from sqlalchemy import ForeignKey, String, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TenantMixin, TimestampMixin


class Role(str, enum.Enum):
    ADMIN = "ADMIN"
    MONITOR = "MONITOR"
    MODEL = "MODEL"


class User(TenantMixin, TimestampMixin, Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    email: Mapped[str] = mapped_column(String(320), unique=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(512), nullable=False)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[Role] = mapped_column(default=Role.MODEL, nullable=False)
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)

    tenant: Mapped["Tenant"] = relationship(back_populates="users")  # noqa: F821
    shifts: Mapped[list["Shift"]] = relationship(back_populates="model")  # noqa: F821
    technical_sheets: Mapped[list["TechnicalSheet"]] = relationship(  # noqa: F821
        back_populates="model"
    )
