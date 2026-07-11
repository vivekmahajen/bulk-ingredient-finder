"""TranslationService: degradation, circuit breaker, script detection."""

from __future__ import annotations

import pytest

from app.services.translation import (
    CircuitBreaker,
    NullProvider,
    TranslationService,
    detect_by_script,
)


@pytest.mark.asyncio
async def test_english_is_passthrough() -> None:
    svc = TranslationService(NullProvider())
    out = await svc.to_english(display_name="Turmeric", source_lang="en")
    assert out.canonical_en == "Turmeric"
    assert out.needs_review is False


@pytest.mark.asyncio
async def test_failure_degrades_to_needs_review() -> None:
    class Boom:
        name = "boom"

        async def detect(self, text):  # noqa: ANN001
            raise RuntimeError("x")

        async def translate(self, text, *, source, target="en"):  # noqa: ANN001
            raise RuntimeError("down")

        async def romanize(self, text, *, source):  # noqa: ANN001
            return None

    svc = TranslationService(Boom())
    out = await svc.to_english(display_name="हल्दी", source_lang="hi")
    assert out.canonical_en == "हल्दी"
    assert out.needs_review is True


def test_circuit_breaker_opens_after_threshold() -> None:
    breaker = CircuitBreaker(threshold=2, cooldown_s=60)
    assert not breaker.is_open
    breaker.record_failure()
    assert not breaker.is_open
    breaker.record_failure()
    assert breaker.is_open
    breaker.record_success()
    assert not breaker.is_open


def test_script_detection() -> None:
    assert detect_by_script("हल्दी").lang == "hi"
    assert detect_by_script("Turmeric").lang == "en"
    assert detect_by_script("김치").lang == "ko"
