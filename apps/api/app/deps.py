"""Request-scoped dependencies: the org/user context every handler runs under.

Full authentication lands in PR-1. Until then this resolves the acting org the
way dogfood mode needs:

  * ``MULTI_TENANT=false`` -> the single seeded org.
  * otherwise -> the org named by the ``X-Org-Id`` header (validated), so the
    multi-tenant surface can be exercised before real auth exists.

The acting user is the org's first user when present (nullable — audit rows
tolerate a missing user).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from fastapi import Depends, Header, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.errors import ProblemException
from app.db.session import get_session
from app.repositories.tenancy import OrgRepository, UserRepository


@dataclass(frozen=True)
class RequestContext:
    org_id: uuid.UUID
    user_id: uuid.UUID | None


async def get_context(
    session: AsyncSession = Depends(get_session),
    x_org_id: str | None = Header(default=None, alias="X-Org-Id"),
) -> RequestContext:
    orgs = OrgRepository(session)

    if settings.multi_tenant and x_org_id:
        try:
            org_id = uuid.UUID(x_org_id)
        except ValueError as exc:
            raise ProblemException(
                status_code=status.HTTP_400_BAD_REQUEST,
                title="Invalid X-Org-Id",
                detail="X-Org-Id must be a UUID.",
            ) from exc
        org = await orgs.get(org_id)
    else:
        org = await orgs.get_default()

    if org is None:
        raise ProblemException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            title="No organization configured",
            detail="No org is available. Run `make seed` to bootstrap the dogfood org.",
        )

    user = await UserRepository(session).first_for_org(org.id)
    return RequestContext(org_id=org.id, user_id=user.id if user else None)
