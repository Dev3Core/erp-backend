import enum
import uuid

from sqlalchemy import ForeignKey, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TenantMixin, TimestampMixin


class Platform(str, enum.Enum):
    CHATURBATE = "CHATURBATE"
    STRIPCHAT = "STRIPCHAT"


class RoomStatus(str, enum.Enum):
    ONLINE = "ONLINE"
    OFFLINE = "OFFLINE"
    INCIDENT = "INCIDENT"


class Room(TenantMixin, TimestampMixin, Base):
    __tablename__ = "rooms"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    platform: Mapped[Platform] = mapped_column(nullable=False)
    url: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[RoomStatus] = mapped_column(default=RoomStatus.OFFLINE, nullable=False)
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)

    tenant: Mapped["Tenant"] = relationship(back_populates="rooms")  # noqa: F821
    shifts: Mapped[list["Shift"]] = relationship(back_populates="room")  # noqa: F821
