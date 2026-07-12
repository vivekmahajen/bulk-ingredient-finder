"""Compare service: rank stores per ingredient + basket optimization.

The core "where is it cheapest" logic:
  * eligible stores = within radius OR (include_delivery AND store delivers);
  * per ingredient, take the latest price per store, drop entries staler than 90d
    unless nothing fresher exists, rank ascending by normalized unit price;
  * basket math compares one-store vs best-per-item vs a greedy two-store split.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from app.deps import RequestContext
from app.models.ingredient import Ingredient
from app.repositories.compare import CompareRepository
from app.repositories.stores import StoreRepository
from app.repositories.tenancy import OrgRepository
from app.schemas.compare import (
    BasketStoreTotal,
    BasketSummary,
    CompareResponse,
    IngredientCompare,
    SplitSuggestion,
    StoreOption,
)

STALE_COMPARE_DAYS = 90
SPLIT_MIN_SAVING = Decimal("0.10")  # switch an item only if it saves > 10%


def _cents(value: Decimal) -> int:
    return int(value.quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def confidence(source: str, age_days: int) -> str:
    if source == "invoice" and age_days <= 30:
        return "high"
    if source in {"shelf", "quote"} and age_days <= 45:
        return "medium"
    return "low"


@dataclass
class _Priced:
    store_id: uuid.UUID
    store_name: str
    store_kind: str | None
    brand: str | None
    unit_price: Decimal
    price_cents: int
    pack_desc: str
    base_unit: str
    observed_at: date
    age_days: int
    delivers: bool
    source: str


async def _eligible_stores(
    session: AsyncSession,
    ctx: RequestContext,
    radius_km: float | None,
    include_delivery: bool,
) -> tuple[dict[uuid.UUID, float | None], set[uuid.UUID], int]:
    org = await OrgRepository(session).get(ctx.org_id)
    center = (
        (float(org.home_lat), float(org.home_lng))
        if org and org.home_lat is not None and org.home_lng is not None
        else (None, None)
    )
    rows = await StoreRepository(session, ctx.org_id).list_stores(
        center_lat=center[0], center_lng=center[1]
    )
    distances: dict[uuid.UUID, float | None] = {}
    eligible: set[uuid.UUID] = set()
    for r in rows:
        dist = float(r.distance_km) if r.distance_km is not None else None
        distances[r.id] = dist
        if radius_km is None:
            eligible.add(r.id)
        elif (dist is not None and dist <= radius_km) or (include_delivery and r.delivers):
            eligible.add(r.id)
    return distances, eligible, len(rows)


async def compare(
    session: AsyncSession,
    ctx: RequestContext,
    *,
    ingredients: list[Ingredient],
    radius_km: float | None,
    include_delivery: bool,
    quantities: dict[uuid.UUID, float] | None = None,
    today: date | None = None,
) -> CompareResponse:
    today = today or date.today()
    quantities = quantities or {}
    notes: list[str] = []

    distances, eligible_ids, store_count = await _eligible_stores(
        session, ctx, radius_km, include_delivery
    )
    repo = CompareRepository(session, ctx.org_id)
    rows = await repo.latest_per_store([i.id for i in ingredients], list(eligible_ids))

    by_ingredient: dict[uuid.UUID, list[_Priced]] = {i.id: [] for i in ingredients}
    for r in rows:
        if r.unit_price_cents is None:
            continue
        age = max(0, (today - r.observed_at).days)
        by_ingredient[r.ingredient_id].append(
            _Priced(
                store_id=r.store_id,
                store_name=r.store_name,
                store_kind=str(r.store_kind) if r.store_kind is not None else None,
                brand=r.brand,
                unit_price=Decimal(str(r.unit_price_cents)),
                price_cents=r.price_cents,
                pack_desc=r.pack_desc,
                base_unit=r.base_unit,
                observed_at=r.observed_at,
                age_days=age,
                delivers=r.delivers,
                source=str(r.source),
            )
        )

    results: list[IngredientCompare] = []
    # price[ingredient][store] used by the basket math below.
    price_matrix: dict[uuid.UUID, dict[uuid.UUID, _Priced]] = {}

    for ing in ingredients:
        priced = by_ingredient.get(ing.id, [])
        if priced and any(p.age_days <= STALE_COMPARE_DAYS for p in priced):
            priced = [p for p in priced if p.age_days <= STALE_COMPARE_DAYS]
        priced.sort(key=lambda p: p.unit_price)
        base_unit = priced[0].base_unit if priced else "kg"
        worst = max((p.unit_price for p in priced), default=Decimal(0))

        options = [
            StoreOption(
                store_id=p.store_id,
                store_name=p.store_name,
                store_kind=p.store_kind,
                brand=p.brand,
                unit_price_cents=float(p.unit_price),
                base_unit=p.base_unit,
                pack_desc=p.pack_desc,
                price_cents=p.price_cents,
                observed_at=p.observed_at,
                age_days=p.age_days,
                distance_km=distances.get(p.store_id),
                delivers=p.delivers,
                confidence=confidence(p.source, p.age_days),
                savings_vs_worst_pct=(
                    float((worst - p.unit_price) / worst * 100) if worst > 0 else 0.0
                ),
            )
            for p in priced
        ]
        results.append(
            IngredientCompare(
                ingredient_id=ing.id,
                canonical_name_en=ing.canonical_name_en,
                base_unit=base_unit,
                best_store_id=priced[0].store_id if priced else None,
                options=options,
            )
        )
        price_matrix[ing.id] = {p.store_id: p for p in priced}

    basket = _basket_summary(ingredients, price_matrix, quantities, notes)
    if radius_km is not None and not eligible_ids:
        notes.append("No stores fall within the radius or offer delivery.")

    return CompareResponse(
        ingredients=results,
        basket_summary=basket,
        radius_km=radius_km,
        include_delivery=include_delivery,
        store_count=store_count,
        notes=notes,
    )


def _basket_summary(
    ingredients: list[Ingredient],
    price_matrix: dict[uuid.UUID, dict[uuid.UUID, _Priced]],
    quantities: dict[uuid.UUID, float],
    notes: list[str],
) -> BasketSummary | None:
    participating = [i for i in ingredients if price_matrix.get(i.id)]
    if not participating:
        return None

    qty: dict[uuid.UUID, Decimal] = {
        i.id: Decimal(str(quantities.get(i.id, 1.0))) for i in participating
    }

    # Best-per-item total: each ingredient at its cheapest store.
    best_per_item = Decimal(0)
    for i in participating:
        cheapest = min(price_matrix[i.id].values(), key=lambda p: p.unit_price)
        best_per_item += qty[i.id] * cheapest.unit_price

    # Single store: cheapest store that prices every participating ingredient.
    store_names: dict[uuid.UUID, str] = {}
    coverage: dict[uuid.UUID, int] = {}
    store_totals: dict[uuid.UUID, Decimal] = {}
    for i in participating:
        for sid, p in price_matrix[i.id].items():
            store_names[sid] = p.store_name
            coverage[sid] = coverage.get(sid, 0) + 1
            store_totals[sid] = store_totals.get(sid, Decimal(0)) + qty[i.id] * p.unit_price

    full_carriers = [sid for sid in store_totals if coverage[sid] == len(participating)]
    single_store: BasketStoreTotal | None = None
    split: SplitSuggestion | None = None
    if full_carriers:
        primary_id = min(full_carriers, key=lambda sid: store_totals[sid])
        primary_total = store_totals[primary_id]
        single_store = BasketStoreTotal(
            store_id=primary_id,
            store_name=store_names[primary_id],
            total_cents=_cents(primary_total),
            covers=len(participating),
        )
        split = _split(participating, price_matrix, qty, primary_id, primary_total, store_names)
    else:
        notes.append("No single store carries every item — showing best-per-item only.")

    single_cents = single_store.total_cents if single_store else _cents(best_per_item)
    return BasketSummary(
        single_store=single_store,
        best_per_item_total_cents=_cents(best_per_item),
        split=split,
        savings_best_vs_single_cents=max(0, single_cents - _cents(best_per_item)),
    )


def _split(
    participating: list[Ingredient],
    price_matrix: dict[uuid.UUID, dict[uuid.UUID, _Priced]],
    qty: dict[uuid.UUID, Decimal],
    primary_id: uuid.UUID,
    primary_total: Decimal,
    store_names: dict[uuid.UUID, str],
) -> SplitSuggestion:
    # Greedy secondary: the store that saves the most by taking only the items
    # where it beats the primary by more than 10%.
    best_secondary: uuid.UUID | None = None
    best_saving = Decimal(0)
    for sid in store_names:
        if sid == primary_id:
            continue
        saving = Decimal(0)
        for i in participating:
            prim = price_matrix[i.id].get(primary_id)
            alt = price_matrix[i.id].get(sid)
            if prim is None or alt is None:
                continue
            if alt.unit_price < prim.unit_price * (1 - SPLIT_MIN_SAVING):
                saving += qty[i.id] * (prim.unit_price - alt.unit_price)
        if saving > best_saving:
            best_saving = saving
            best_secondary = sid

    secondary = None
    if best_secondary is not None:
        secondary = BasketStoreTotal(
            store_id=best_secondary,
            store_name=store_names[best_secondary],
            total_cents=_cents(best_saving),  # dollars moved to the secondary
            covers=sum(
                1
                for i in participating
                if best_secondary in price_matrix[i.id]
                and price_matrix[i.id][best_secondary].unit_price
                < price_matrix[i.id][primary_id].unit_price * (1 - SPLIT_MIN_SAVING)
            ),
        )
    return SplitSuggestion(
        primary=BasketStoreTotal(
            store_id=primary_id,
            store_name=store_names[primary_id],
            total_cents=_cents(primary_total),
            covers=len(participating),
        ),
        secondary=secondary,
        total_cents=_cents(primary_total - best_saving),
        savings_vs_single_cents=_cents(best_saving),
    )
