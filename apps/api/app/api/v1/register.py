"""Org registration (PR-8) — gated behind the MULTI_TENANT flag.

In dogfood mode (MULTI_TENANT=false) self-registration is disabled; the single
org is created by the seed. Full auth (password/magic-link) lands in PR-1; this is
the org-bootstrap surface the flag controls.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.errors import ProblemException
from app.db.session import get_session
from app.models.enums import Role
from app.models.org import Org
from app.models.user import User
from app.repositories.tenancy import UserRepository
from app.schemas.user import MeRead, OrgBrief, RegisterRequest

router = APIRouter(prefix="/register", tags=["auth"])


@router.post("", response_model=MeRead, status_code=status.HTTP_201_CREATED, summary="Register org")
async def register(
    payload: RegisterRequest,
    session: AsyncSession = Depends(get_session),
) -> MeRead:
    if not settings.multi_tenant:
        raise ProblemException(
            status_code=status.HTTP_403_FORBIDDEN,
            title="Registration disabled",
            detail="Self-registration is off in single-restaurant (dogfood) mode.",
        )
    if await UserRepository(session).get_by_email(payload.email) is not None:
        raise ProblemException(
            status_code=status.HTTP_409_CONFLICT,
            title="Email already registered",
            detail=payload.email,
        )
    org = Org(name=payload.org_name)
    session.add(org)
    await session.flush()
    user = User(
        org_id=org.id,
        email=payload.email,
        display_name=payload.display_name,
        locale=payload.locale,
        role=Role.OWNER,
    )
    session.add(user)
    await session.commit()
    return MeRead(
        id=user.id,
        email=user.email,
        display_name=user.display_name,
        locale=user.locale,
        role=user.role,
        org=OrgBrief.model_validate(org),
    )
