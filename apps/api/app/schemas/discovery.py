"""Web price-discovery schemas.

These describe *estimated* sellers/prices gathered from the open web (not
verified invoices). Every field except ``name`` is optional because a given
listing may only surface a name + a link.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class DiscoveredSeller(BaseModel):
    name: str
    # Raw price string as it appeared, kept verbatim for transparency.
    price_text: str | None = None
    # Best-effort structured pack price.
    price_cents: int | None = None
    pack_desc: str | None = None
    pack_qty: float | None = None
    pack_unit: str | None = None  # one of PackUnit values when known
    # Normalized (server-computed from the fields above) for comparison.
    unit_price_cents: float | None = None
    base_unit: str | None = None
    # Provenance.
    url: str | None = None
    location: str | None = None
    distance_note: str | None = None  # free-text proximity ("~18 mi, Redding")
    snippet: str | None = None


class DiscoverResponse(BaseModel):
    configured: bool
    query: str
    sellers: list[DiscoveredSeller] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)
    disclaimer: str = (
        "Estimated from public web sources — verify pricing and availability with "
        "the seller before ordering."
    )
