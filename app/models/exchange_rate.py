import uuid
from datetime import date

from sqlalchemy import Date, Numeric, text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class ExchangeRate(TimestampMixin, Base):
    __tablename__ = "exchange_rates"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    rate_date: Mapped[date] = mapped_column(Date, unique=True, nullable=False)
    cop_per_usd: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    source: Mapped[str] = mapped_column(default="Banco de la Republica", nullable=False)
