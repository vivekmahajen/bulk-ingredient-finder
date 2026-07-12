"""Org + user lookups.

``orgs`` is the tenant boundary itself (no ``org_id`` column), so these are plain
repositories rather than :class:`OrgScopedRepository` subclasses. They live in the
repository layer so all ``select(...)`` usage stays in one place.
"""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.org import Org
from app.models.user import User


class OrgRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get(self, org_id: uuid.UUID) -> Org | None:
        result = await self.session.execute(select(Org).where(Org.id == org_id))
        return result.scalar_one_or_none()

    async def get_default(self) -> Org | None:
        """The single dogfood org (earliest created). Used when MULTI_TENANT=false."""
        result = await self.session.execute(select(Org).order_by(Org.created_at).limit(1))
        return result.scalars().first()

    async def get_by_name(self, name: str) -> Org | None:
        result = await self.session.execute(select(Org).where(Org.name == name))
        return result.scalar_one_or_none()


class UserRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get(self, user_id: uuid.UUID) -> User | None:
        result = await self.session.execute(select(User).where(User.id == user_id))
        return result.scalar_one_or_none()

    async def get_by_email(self, email: str) -> User | None:
        result = await self.session.execute(select(User).where(User.email == email))
        return result.scalar_one_or_none()

    async def first_for_org(self, org_id: uuid.UUID) -> User | None:
        result = await self.session.execute(
            select(User).where(User.org_id == org_id).order_by(User.created_at).limit(1)
        )
        return result.scalars().first()
