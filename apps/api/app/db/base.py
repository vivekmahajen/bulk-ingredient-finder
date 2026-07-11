"""SQLAlchemy declarative base + shared column mixins.

Domain models (PR-2+) subclass ``Base``. Keeping the metadata here lets Alembic's
autogenerate discover tables via ``Base.metadata`` without importing the app.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Declarative base for all ORM models."""


class UUIDPrimaryKeyMixin:
    """Adds a UUID primary key defaulted server-side via ``gen_random_uuid()``."""

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=func.gen_random_uuid(),
    )


class TimestampMixin:
    """Adds ``created_at`` / ``updated_at`` maintained server-side."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class OrgScopedMixin:
    """Every domain row belongs to exactly one org (restaurant).

    The presence of ``org_id`` on every domain table is the backbone of tenant
    isolation; queries must go through the repository layer's
    ``get_org_scoped_query`` so the filter is never skipped (enforced by
    ``tests/test_org_scoping.py``).
    """

    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("orgs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
