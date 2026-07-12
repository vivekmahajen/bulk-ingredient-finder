"""Curated culinary-synonym lookup (Python side).

Loads ``packages/shared/culinary_synonyms.json`` — the single source shared with
``packages/shared/src/synonyms.ts``. A drift test asserts known pairs on both
sides; because both read the same file they cannot diverge.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path


@dataclass(frozen=True)
class SynonymTerm:
    alias: str
    lang: str


@dataclass(frozen=True)
class SynonymGroup:
    canonical_en: str
    terms: tuple[SynonymTerm, ...]


def _synonyms_path() -> Path:
    override = os.environ.get("RASOI_SYNONYMS_PATH")
    if override:
        return Path(override)
    # apps/api/app/synonyms.py -> repo root is parents[3]
    return Path(__file__).resolve().parents[3] / "packages" / "shared" / "culinary_synonyms.json"


@lru_cache
def load_groups() -> tuple[SynonymGroup, ...]:
    data = json.loads(_synonyms_path().read_text(encoding="utf-8"))
    groups: list[SynonymGroup] = []
    for g in data["groups"]:
        terms = tuple(SynonymTerm(alias=t["alias"], lang=t["lang"]) for t in g["terms"])
        groups.append(SynonymGroup(canonical_en=g["canonical_en"], terms=terms))
    return tuple(groups)


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
