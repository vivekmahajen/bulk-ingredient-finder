"""Request-scoped dependencies: the org/user context every handler runs under.

Resolution order:
  1. A valid access-JWT cookie (PR-1 auth) -> that user's org + id + role.
  2. Otherwise, dogfood/dev fallback:
       * ``MULTI_TENANT=false`` -> the single seeded org;
       * otherwise -> the org named by the ``X-Org-Id`` header.

The dogfood fallback keeps the app usable before a user signs in; once auth is
wired end-to-end the JWT path is authoritative.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable, Coroutine
from dataclasses import dataclass
from typing import Any

import jwt
from fastapi import Depends, Header, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import security
from app.core.config import settings
from app.core.cookies import ACCESS_COOKIE, CSRF_COOKIE, CSRF_HEADER
from app.core.errors import ProblemException
from app.db.session import get_session
from app.models.enums import Role
from app.repositories.tenancy import OrgRepository, UserRepository


@dataclass(frozen=True)
class RequestContext:
    org_id: uuid.UUID
    user_id: uuid.UUID | None
    role: Role | None = None


def _claims_from_request(request: Request) -> dict[str, Any] | None:
    token = request.cookies.get(ACCESS_COOKIE)
    if not token:
        return None
    try:
        return security.decode_access_token(token)
    except jwt.PyJWTError:
        return None


async def get_context(
    request: Request,
    session: AsyncSession = Depends(get_session),
    x_org_id: str | None = Header(default=None, alias="X-Org-Id"),
) -> RequestContext:
    # 1. Authenticated: derive org/user/role from the access JWT.
    claims = _claims_from_request(request)
    if claims is not None:
        try:
            return RequestContext(
                org_id=uuid.UUID(claims["org"]),
                user_id=uuid.UUID(claims["sub"]),
                role=Role(claims["role"]),
            )
        except (KeyError, ValueError):
            pass  # fall through to dogfood resolution

    # 2. Dogfood/dev fallback.
    orgs = OrgRepository(session)
    if settings.multi_tenant:
        # Multi-tenant: no valid session -> no implicit org. A dev override via
        # X-Org-Id is still honored so the surface can be exercised pre-auth.
        if not x_org_id:
            raise ProblemException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                title="Authentication required",
                detail="Sign in to continue.",
            )
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
    return RequestContext(
        org_id=org.id,
        user_id=user.id if user else None,
        role=user.role if user else None,
    )


async def require_user(ctx: RequestContext = Depends(get_context)) -> RequestContext:
    """Reject unauthenticated requests (no resolvable user)."""
    if ctx.user_id is None:
        raise ProblemException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            title="Authentication required",
            detail="Sign in to continue.",
        )
    return ctx


def require_role(
    *roles: Role,
) -> Callable[[RequestContext], Coroutine[Any, Any, RequestContext]]:
    async def _guard(ctx: RequestContext = Depends(require_user)) -> RequestContext:
        if ctx.role not in roles:
            raise ProblemException(
                status_code=status.HTTP_403_FORBIDDEN,
                title="Insufficient role",
                detail=f"Requires one of: {', '.join(r.value for r in roles)}.",
            )
        return ctx

    return _guard


async def require_csrf(request: Request) -> None:
    """Double-submit CSRF check for mutating requests: the ``X-CSRF-Token`` header
    must match the ``rr_csrf`` cookie. Skipped when unauthenticated (no cookie)."""
    csrf_cookie = request.cookies.get(CSRF_COOKIE)
    if not csrf_cookie:
        return
    header = request.headers.get(CSRF_HEADER)
    if not header or not security.constant_time_equals(header, csrf_cookie):
        raise ProblemException(
            status_code=status.HTTP_403_FORBIDDEN,
            title="CSRF check failed",
            detail="Missing or invalid CSRF token.",
        )
