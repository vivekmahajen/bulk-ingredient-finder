"""Store (supplier) model."""

from __future__ import annotations

from sqlalchemy import Boolean, Numeric, Text
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, OrgScopedMixin, TimestampMixin, UUIDPrimaryKeyMixin
from app.models._sa_enum import pg_enum
from app.models.enums import StoreKind


class Store(UUIDPrimaryKeyMixin, OrgScopedMixin, TimestampMixin, Base):
    __tablename__ = "stores"

    name: Mapped[str] = mapped_column(Text, nullable=False)
    kind: Mapped[StoreKind] = mapped_column(pg_enum(StoreKind, "store_kind"), nullable=False)
    address_line: Mapped[str | None] = mapped_column(Text, nullable=True)
    city: Mapped[str | None] = mapped_column(Text, nullable=True)
    state: Mapped[str | None] = mapped_column(Text, nullable=True)
    postal: Mapped[str | None] = mapped_column(Text, nullable=True)
    lat: Mapped[float | None] = mapped_column(Numeric, nullable=True)
    lng: Mapped[float | None] = mapped_column(Numeric, nullable=True)
    website: Mapped[str | None] = mapped_column(Text, nullable=True)
    phone: Mapped[str | None] = mapped_column(Text, nullable=True)
    delivers: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    delivery_days: Mapped[list[str] | None] = mapped_column(ARRAY(Text), nullable=True)
    min_order: Mapped[float | None] = mapped_column(Numeric, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
    )
