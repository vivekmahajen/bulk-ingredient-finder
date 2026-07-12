"""Audit-log writer.

A thin helper so mutating handlers (ingredient/alias/store changes in PR-3/PR-5)
record who did what. Adds the row to the session; the caller's transaction commits
it alongside the mutation.
"""

from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit import AuditLog


def record(
    session: AsyncSession,
    *,
    org_id: uuid.UUID,
    user_id: uuid.UUID | None,
    action: str,
    entity: str,
    entity_id: uuid.UUID | None = None,
    meta: dict[str, object] | None = None,
) -> AuditLog:
    entry = AuditLog(
        org_id=org_id,
        user_id=user_id,
        action=action,
        entity=entity,
        entity_id=entity_id,
        meta=meta or {},
    )
    session.add(entry)
    return entry
