"""Org (restaurant) model.

In dogfood mode (``MULTI_TENANT=false``) a single org is created by the seed.
``home_lat`` / ``home_lng`` (the restaurant's location, used for store-distance
math) are added in PR-5.
"""

from __future__ import annotations

from sqlalchemy import Numeric, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class Org(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "orgs"

    name: Mapped[str] = mapped_column(Text, nullable=False)
    # The restaurant's own location, for store-distance math (PR-5+).
    home_lat: Mapped[float | None] = mapped_column(Numeric, nullable=True)
    home_lng: Mapped[float | None] = mapped_column(Numeric, nullable=True)
