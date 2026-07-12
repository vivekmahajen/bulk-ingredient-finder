"""Org-scoping guardrail.

Enforces the invariant that raw ``select(`` statements only ever appear in the
repository layer, so no handler or service can build an unscoped query that leaks
across tenants. If you need a new query, add it to a repository.
"""

from __future__ import annotations

import re
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent.parent / "app"

# The only place raw select() is allowed.
ALLOWED_PREFIX = APP_DIR / "repositories"

_SELECT_RE = re.compile(r"\bselect\s*\(")


def test_no_raw_select_outside_repository_layer() -> None:
    offenders: list[str] = []
    for path in APP_DIR.rglob("*.py"):
        if ALLOWED_PREFIX in path.parents or path == ALLOWED_PREFIX:
            continue
        text = path.read_text(encoding="utf-8")
        for lineno, line in enumerate(text.splitlines(), start=1):
            stripped = line.strip()
            if stripped.startswith("#"):
                continue
            if _SELECT_RE.search(line):
                rel = path.relative_to(APP_DIR.parent)
                offenders.append(f"{rel}:{lineno}: {stripped}")

    assert not offenders, (
        "Raw select() found outside app/repositories/. Route queries through the "
        "repository layer so org scoping is never skipped:\n" + "\n".join(offenders)
    )
