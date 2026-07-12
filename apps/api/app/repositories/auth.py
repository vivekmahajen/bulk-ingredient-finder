"""Auth-token repository (global; keyed by user, not org)."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.auth_token import AuthToken
from app.models.enums import AuthTokenKind


class AuthTokenRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    def add(
        self,
        *,
        user_id: uuid.UUID,
        kind: AuthTokenKind,
        token_hash: str,
        expires_at: datetime,
        family_id: uuid.UUID | None = None,
    ) -> AuthToken:
        token = AuthToken(
            user_id=user_id,
            kind=kind,
            token_hash=token_hash,
            expires_at=expires_at,
            family_id=family_id,
        )
        self.session.add(token)
        return token

    async def get_by_hash(self, token_hash: str, kind: AuthTokenKind) -> AuthToken | None:
        stmt = select(AuthToken).where(AuthToken.token_hash == token_hash, AuthToken.kind == kind)
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def mark_used(self, token: AuthToken, when: datetime) -> None:
        token.used_at = when

    async def revoke_family(self, family_id: uuid.UUID, when: datetime) -> None:
        """Reuse detection: burn every refresh token in the rotation chain."""
        await self.session.execute(
            update(AuthToken)
            .where(AuthToken.family_id == family_id, AuthToken.used_at.is_(None))
            .values(used_at=when)
        )

    async def revoke_all_for_user(
        self, user_id: uuid.UUID, kind: AuthTokenKind, when: datetime
    ) -> None:
        await self.session.execute(
            update(AuthToken)
            .where(
                AuthToken.user_id == user_id,
                AuthToken.kind == kind,
                AuthToken.used_at.is_(None),
            )
            .values(used_at=when)
        )
