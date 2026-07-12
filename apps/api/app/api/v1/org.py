"""Org settings endpoints (PR-5): read + set the restaurant's home location."""

from __future__ import annotations

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ProblemException
from app.db.session import get_session
from app.deps import RequestContext, get_context
from app.repositories.tenancy import OrgRepository
from app.schemas.store import OrgRead, OrgUpdate
from app.services import audit
from app.services.geocode import GeocodeService, get_geocode_service

router = APIRouter(prefix="/org", tags=["org"])


@router.get("", response_model=OrgRead, summary="Get the current org")
async def get_org(
    ctx: RequestContext = Depends(get_context),
    session: AsyncSession = Depends(get_session),
) -> OrgRead:
    org = await OrgRepository(session).get(ctx.org_id)
    if org is None:
        raise ProblemException(
            status_code=status.HTTP_404_NOT_FOUND, title="Org not found", detail=str(ctx.org_id)
        )
    return OrgRead.model_validate(org)


@router.patch("", response_model=OrgRead, summary="Update org name / home location")
async def update_org(
    payload: OrgUpdate,
    ctx: RequestContext = Depends(get_context),
    session: AsyncSession = Depends(get_session),
    geocoder: GeocodeService = Depends(get_geocode_service),
) -> OrgRead:
    org = await OrgRepository(session).get(ctx.org_id)
    if org is None:
        raise ProblemException(
            status_code=status.HTTP_404_NOT_FOUND, title="Org not found", detail=str(ctx.org_id)
        )

    changes = payload.model_dump(exclude_unset=True)
    if "name" in changes and changes["name"]:
        org.name = changes["name"]
    if "home_lat" in changes:
        org.home_lat = changes["home_lat"]
    if "home_lng" in changes:
        org.home_lng = changes["home_lng"]
    # Geocode a home address when explicit coords weren't provided.
    if payload.home_address and "home_lat" not in changes and "home_lng" not in changes:
        result = await geocoder.locate(payload.home_address)
        if result is not None:
            org.home_lat = result.lat
            org.home_lng = result.lng

    audit.record(
        session,
        org_id=ctx.org_id,
        user_id=ctx.user_id,
        action="org.update",
        entity="org",
        entity_id=org.id,
        meta={"fields": list(changes.keys())},
    )
    await session.commit()
    await session.refresh(org)
    return OrgRead.model_validate(org)
