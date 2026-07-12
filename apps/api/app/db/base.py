"""SQLAlchemy declarative base.

Domain models (PR-2+) subclass ``Base``. Keeping the metadata here lets Alembic's
autogenerate discover tables via ``Base.metadata`` without importing the app.
"""

from __future__ import annotations

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Declarative base for all ORM models."""
