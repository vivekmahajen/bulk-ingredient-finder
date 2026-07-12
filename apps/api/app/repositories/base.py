"""Base org-scoped repository."""

from __future__ import annotations

import uuid
from typing import Generic, TypeVar

from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import Base

ModelT = TypeVar("ModelT", bound=Base)


class OrgScopedRepository(Generic[ModelT]):
    """Base class binding a session + org so every query filters on ``org_id``."""

    model: type[ModelT]

    def __init__(self, session: AsyncSession, org_id: uuid.UUID) -> None:
        self.session = session
        self.org_id = org_id

    def scoped(self) -> Select[tuple[ModelT]]:
        """A ``select`` over ``model`` pre-filtered to this repository's org.

        All reads MUST start from this method so the org filter is never omitted.
        """
        return select(self.model).where(self.model.org_id == self.org_id)  # type: ignore[attr-defined]

    async def get(self, entity_id: uuid.UUID) -> ModelT | None:
        result = await self.session.execute(
            self.scoped().where(self.model.id == entity_id)  # type: ignore[attr-defined]
        )
        return result.scalar_one_or_none()

    async def list_active(self) -> list[ModelT]:
        stmt = self.scoped()
        if hasattr(self.model, "is_active"):
            stmt = stmt.where(self.model.is_active.is_(True))  # type: ignore[attr-defined]
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    def add(self, entity: ModelT) -> ModelT:
        self.session.add(entity)
        return entity
