"""Match extracted invoice lines to org ingredients + guess the vendor store.

Reuses the PR-4 trigram search (canonical + aliases, unaccent) so a Hindi line
like "जीरा"/"jeera" resolves to cumin via existing synonyms — no new matching
machinery. Matching never persists a store on the invoice; the vendor guess is
advisory and confirmed by a human at commit.
"""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass
from difflib import SequenceMatcher

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import LineMatchStatus
from app.models.invoice import InvoiceLine
from app.repositories.search import SearchRepository
from app.repositories.stores import StoreRepository

AUTO_MATCH_THRESHOLD = 0.55
SUGGEST_THRESHOLD = 0.30
VENDOR_GUESS_THRESHOLD = 0.40


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9 ]", " ", s.lower()).strip()


def _is_fee(line: InvoiceLine) -> bool:
    desc = (line.description_en or "").strip().upper()
    return desc.startswith("FEE:")


@dataclass(frozen=True)
class Candidate:
    ingredient_id: uuid.UUID
    canonical_name_en: str
    score: float


@dataclass(frozen=True)
class StoreGuessResult:
    store_id: uuid.UUID
    name: str
    score: float


async def match_lines(session: AsyncSession, org_id: uuid.UUID, lines: list[InvoiceLine]) -> None:
    """Set match_status / matched_ingredient_id / match_score on each line in place."""
    repo = SearchRepository(session, org_id)
    for line in lines:
        if _is_fee(line):
            line.match_status = LineMatchStatus.EXCLUDED
            line.matched_ingredient_id = None
            line.match_score = None
            continue

        query = (line.description_en or line.raw_text or "").strip()
        rows = await repo.search(q=query, limit=1) if query else []
        if not rows and line.raw_text and line.raw_text.strip() != query:
            rows = await repo.search(q=line.raw_text.strip(), limit=1)

        best = rows[0] if rows else None
        score = float(best.score) if best is not None else 0.0
        if best is not None and score >= AUTO_MATCH_THRESHOLD:
            line.match_status = LineMatchStatus.AUTO_MATCHED
            line.matched_ingredient_id = best.id
            line.match_score = score
        elif best is not None and score >= SUGGEST_THRESHOLD:
            line.match_status = LineMatchStatus.SUGGESTED
            line.matched_ingredient_id = None
            line.match_score = score
        else:
            line.match_status = LineMatchStatus.UNMATCHED
            line.matched_ingredient_id = None
            line.match_score = score or None


async def candidates_for(
    session: AsyncSession, org_id: uuid.UUID, query: str, *, limit: int = 3
) -> list[Candidate]:
    if not query.strip():
        return []
    rows = await SearchRepository(session, org_id).search(q=query.strip(), limit=limit)
    return [
        Candidate(ingredient_id=r.id, canonical_name_en=r.canonical_name_en, score=float(r.score))
        for r in rows
    ]


async def guess_store(
    session: AsyncSession, org_id: uuid.UUID, vendor_name: str | None
) -> StoreGuessResult | None:
    if not vendor_name or not vendor_name.strip():
        return None
    target = _norm(vendor_name)
    if not target:
        return None
    stores = await StoreRepository(session, org_id).list_active()
    best: StoreGuessResult | None = None
    for store in stores:
        score = SequenceMatcher(None, target, _norm(store.name)).ratio()
        if best is None or score > best.score:
            best = StoreGuessResult(store_id=store.id, name=store.name, score=score)
    if best is not None and best.score >= VENDOR_GUESS_THRESHOLD:
        return best
    return None
