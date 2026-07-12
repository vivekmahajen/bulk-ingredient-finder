"""Curated culinary-synonym lookup (Python side).

The synonym map is a single logical source, ``culinary_synonyms.json``. It is
vendored into this package (``app/data/``) so it ships inside the API image, and
kept byte-identical to ``packages/shared/culinary_synonyms.json`` (the copy the
web side reads) by a drift test. Both the TS and Python sides assert the same
known pairs, so they cannot diverge.

Synonyms are enrichment, never a hard dependency: if the map can't be located or
parsed the lookup degrades to "no synonyms" rather than raising, so ingredient
creation is never taken down by a packaging/deploy quirk.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from app.core.logging import get_logger

logger = get_logger("synonyms")

_FILENAME = "culinary_synonyms.json"


@dataclass(frozen=True)
class SynonymTerm:
    alias: str
    lang: str


@dataclass(frozen=True)
class SynonymGroup:
    canonical_en: str
    terms: tuple[SynonymTerm, ...]


def _candidate_paths() -> list[Path]:
    """Ordered locations to look for the synonym map.

    1. ``RASOI_SYNONYMS_PATH`` — explicit override.
    2. The copy vendored inside this package (``app/data/``) — the one that
       ships in the deployed image.
    3. The shared monorepo copy (``packages/shared/``) — used in local dev /
       tests where the full repo tree is present.
    """
    candidates: list[Path] = []
    override = os.environ.get("RASOI_SYNONYMS_PATH")
    if override:
        candidates.append(Path(override))

    here = Path(__file__).resolve()
    candidates.append(here.parent / "data" / _FILENAME)

    # Walk up to a plausible repo root without assuming a fixed depth (the
    # deployed layout is shallower than the source tree — a hard-coded
    # ``parents[3]`` there raised IndexError).
    for parent in here.parents:
        candidates.append(parent / "packages" / "shared" / _FILENAME)

    return candidates


def _synonyms_path() -> Path | None:
    for path in _candidate_paths():
        if path.is_file():
            return path
    return None


@lru_cache
def load_groups() -> tuple[SynonymGroup, ...]:
    path = _synonyms_path()
    if path is None:
        logger.warning("synonyms_file_missing", searched=[str(p) for p in _candidate_paths()])
        return ()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        groups: list[SynonymGroup] = []
        for g in data["groups"]:
            terms = tuple(SynonymTerm(alias=t["alias"], lang=t["lang"]) for t in g["terms"])
            groups.append(SynonymGroup(canonical_en=g["canonical_en"], terms=terms))
        return tuple(groups)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        logger.warning("synonyms_load_failed", path=str(path), error=str(exc))
        return ()


@lru_cache
def _index() -> dict[str, SynonymGroup]:
    """Map every canonical name and alias (normalized) to its group."""
    idx: dict[str, SynonymGroup] = {}
    for group in load_groups():
        idx[group.canonical_en.strip().lower()] = group
        for term in group.terms:
            idx.setdefault(term.alias.strip().lower(), group)
    return idx


def find_group(term: str) -> SynonymGroup | None:
    """Find the group a canonical name OR any alias belongs to (case-insensitive)."""
    return _index().get(term.strip().lower())
