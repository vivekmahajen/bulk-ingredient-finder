"""Synonym-map drift test (Python side).

Asserts known culinary pairs resolve to the same group. The TS side
(`apps/web/__tests__/synonyms.test.ts`) asserts the identical pairs; both read
`packages/shared/culinary_synonyms.json`, so they cannot drift.
"""

from __future__ import annotations

import pytest

from app.synonyms import find_group, load_groups

KNOWN_PAIRS = [
    ("haldi", "turmeric"),
    ("jeera", "cumin"),
    ("dhania", "coriander"),
    ("hing", "asafoetida"),
    ("methi", "fenugreek"),
    ("atta", "whole wheat flour"),
    ("maida", "all-purpose flour"),
    ("besan", "gram flour"),
    ("toor dal", "pigeon peas"),
    ("ghee", "clarified butter"),
    ("paneer", "indian cottage cheese"),
    ("elaichi", "cardamom"),
    ("kadi patta", "curry leaves"),
    ("palak", "spinach"),
    ("pyaz", "onion"),
    ("adrak", "ginger"),
    ("lehsun", "garlic"),
]


@pytest.mark.parametrize(("alias", "canonical"), KNOWN_PAIRS)
def test_alias_resolves_to_canonical(alias: str, canonical: str) -> None:
    group = find_group(alias)
    assert group is not None, f"{alias} not found"
    assert group.canonical_en == canonical


def test_lookup_is_case_insensitive() -> None:
    assert find_group("HALDI") is find_group("haldi")


def test_all_groups_have_terms() -> None:
    groups = load_groups()
    assert len(groups) >= 20
    assert all(g.terms for g in groups)
