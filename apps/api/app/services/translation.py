"""Translation / detection / transliteration service.

Two providers behind one protocol:
  * ``GoogleTranslateProvider`` — Cloud Translation v3 (detect + translate +
    romanize where available).
  * ``NullProvider`` — echoes input, script-based detection; used in tests and
    when no provider is configured.

Every provider call goes through :class:`TranslationService`, which enforces a
3s timeout, 2 retries, and a circuit breaker. Translation NEVER blocks ingredient
creation: on any failure the caller falls back to ``canonical = display_name`` and
flags ``needs_review`` (see :meth:`TranslationService.to_english`).
"""

from __future__ import annotations

import asyncio
import time
import unicodedata
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Protocol, TypeVar

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger("translation")

TRANSLATE_TIMEOUT_S = 3.0
TRANSLATE_RETRIES = 2

T = TypeVar("T")


@dataclass(frozen=True)
class DetectionResult:
    lang: str
    confidence: float
    candidates: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class TranslationOutcome:
    """Result of normalizing a term to English."""

    canonical_en: str
    romanization: str | None
    needs_review: bool


class TranslationProvider(Protocol):
    name: str

    async def detect(self, text: str) -> DetectionResult: ...

    async def translate(self, text: str, *, source: str, target: str = "en") -> str: ...

    async def romanize(self, text: str, *, source: str) -> str | None: ...


# --- Script-based helpers (shared by NullProvider + detection heuristics) -----

_SCRIPT_LANG: list[tuple[str, str, list[str]]] = [
    ("DEVANAGARI", "hi", ["hi", "mr", "ne"]),
    ("BENGALI", "bn", ["bn", "as"]),
    ("GURMUKHI", "pa", ["pa"]),
    ("GUJARATI", "gu", ["gu"]),
    ("TAMIL", "ta", ["ta"]),
    ("TELUGU", "te", ["te"]),
    ("HANGUL", "ko", ["ko"]),
    ("HIRAGANA", "ja", ["ja"]),
    ("KATAKANA", "ja", ["ja"]),
    ("CJK", "zh", ["zh", "ja"]),
    ("ARABIC", "ur", ["ur", "ar", "fa"]),
    ("CYRILLIC", "ru", ["ru", "uk"]),
    ("THAI", "th", ["th"]),
]


def _dominant_script(text: str) -> str | None:
    counts: dict[str, int] = {}
    for ch in text:
        if not ch.isalpha():
            continue
        try:
            name = unicodedata.name(ch)
        except ValueError:
            continue
        for token, _, _ in _SCRIPT_LANG:
            if token in name:
                counts[token] = counts.get(token, 0) + 1
                break
    if not counts:
        return None
    return max(counts, key=lambda k: counts[k])


def detect_by_script(text: str) -> DetectionResult:
    """Deterministic script-based detection. Latin/unknown -> English."""
    token = _dominant_script(text)
    if token is None:
        return DetectionResult(lang="en", confidence=0.9, candidates=["en"])
    for tok, lang, candidates in _SCRIPT_LANG:
        if tok == token:
            return DetectionResult(lang=lang, confidence=0.9, candidates=candidates)
    return DetectionResult(lang="en", confidence=0.9, candidates=["en"])


# --- Providers ----------------------------------------------------------------


class NullProvider:
    """Echoes input; detection is script-based; no romanization."""

    name = "null"

    async def detect(self, text: str) -> DetectionResult:
        return detect_by_script(text)

    async def translate(self, text: str, *, source: str, target: str = "en") -> str:
        return text

    async def romanize(self, text: str, *, source: str) -> str | None:
        return None


class GoogleTranslateProvider:
    """Google Cloud Translation v3. Requires TRANSLATE_API_KEY."""

    name = "google"
    _BASE = "https://translation.googleapis.com/language/translate/v2"

    def __init__(self, api_key: str) -> None:
        self._api_key = api_key

    async def detect(self, text: str) -> DetectionResult:
        async with httpx.AsyncClient(timeout=TRANSLATE_TIMEOUT_S) as client:
            resp = await client.post(
                f"{self._BASE}/detect", params={"key": self._api_key, "q": text}
            )
            resp.raise_for_status()
            det = resp.json()["data"]["detections"][0][0]
        lang = det["language"]
        confidence = float(det.get("confidence", 0.0))
        script = detect_by_script(text)
        return DetectionResult(lang=lang, confidence=confidence, candidates=script.candidates)

    async def translate(self, text: str, *, source: str, target: str = "en") -> str:
        async with httpx.AsyncClient(timeout=TRANSLATE_TIMEOUT_S) as client:
            resp = await client.post(
                self._BASE,
                params={"key": self._api_key, "q": text, "source": source, "target": target},
            )
            resp.raise_for_status()
            return str(resp.json()["data"]["translations"][0]["translatedText"])

    async def romanize(self, text: str, *, source: str) -> str | None:
        # v2 has no first-class romanization; transliteration is best-effort and
        # left to the v3 API in a follow-up. Return None rather than guess.
        return None


# --- Circuit breaker ----------------------------------------------------------


class CircuitBreaker:
    """Trips open after ``threshold`` consecutive failures, resets after ``cooldown``."""

    def __init__(self, *, threshold: int = 3, cooldown_s: float = 30.0) -> None:
        self._threshold = threshold
        self._cooldown_s = cooldown_s
        self._failures = 0
        self._opened_at: float | None = None

    @property
    def is_open(self) -> bool:
        if self._opened_at is None:
            return False
        if time.monotonic() - self._opened_at >= self._cooldown_s:
            # half-open: allow a trial call
            self._opened_at = None
            self._failures = 0
            return False
        return True

    def record_success(self) -> None:
        self._failures = 0
        self._opened_at = None

    def record_failure(self) -> None:
        self._failures += 1
        if self._failures >= self._threshold:
            self._opened_at = time.monotonic()


class TranslationUnavailable(Exception):
    pass


# --- Service ------------------------------------------------------------------


class TranslationService:
    """Wraps a provider with timeout, retries, and a circuit breaker."""

    def __init__(self, provider: TranslationProvider, *, breaker: CircuitBreaker | None = None):
        self.provider = provider
        self._breaker = breaker or CircuitBreaker()

    async def _guarded(self, coro_factory: Callable[[], Awaitable[T]], *, op: str) -> T:
        if self._breaker.is_open:
            raise TranslationUnavailable(f"circuit open for {op}")
        last_exc: Exception | None = None
        for attempt in range(TRANSLATE_RETRIES + 1):
            try:
                result = await asyncio.wait_for(coro_factory(), timeout=TRANSLATE_TIMEOUT_S)
                self._breaker.record_success()
                return result
            except Exception as exc:  # noqa: BLE001 — uniform failure handling
                last_exc = exc
                self._breaker.record_failure()
                logger.warning("translation_call_failed", op=op, attempt=attempt, error=str(exc))
        raise TranslationUnavailable(str(last_exc))

    async def detect(self, text: str) -> DetectionResult:
        # Detection must never block ingredient creation — on any provider
        # failure, fall back to the deterministic script-based guess.
        try:
            return await self._guarded(lambda: self.provider.detect(text), op="detect")
        except TranslationUnavailable:
            logger.warning("detect_degraded", text=text)
            return detect_by_script(text)

    async def to_english(self, *, display_name: str, source_lang: str) -> TranslationOutcome:
        """Normalize a term to an English canonical name.

        Never raises: on provider failure returns the display name unchanged and
        flags ``needs_review`` so a human can confirm the translation later.
        """
        if source_lang.split("-")[0] == "en":
            return TranslationOutcome(
                canonical_en=display_name, romanization=None, needs_review=False
            )
        try:
            english = await self._guarded(
                lambda: self.provider.translate(display_name, source=source_lang, target="en"),
                op="translate",
            )
            romanization = await self._guarded(
                lambda: self.provider.romanize(display_name, source=source_lang),
                op="romanize",
            )
            canonical = english.strip() or display_name
            return TranslationOutcome(
                canonical_en=canonical,
                romanization=romanization,
                needs_review=canonical.lower() == display_name.lower(),
            )
        except TranslationUnavailable:
            logger.warning("translation_degraded", display_name=display_name, source=source_lang)
            return TranslationOutcome(
                canonical_en=display_name, romanization=None, needs_review=True
            )


def get_translation_provider() -> TranslationProvider:
    provider = settings.translate_provider.lower()
    if provider == "google" and settings.translate_api_key:
        return GoogleTranslateProvider(settings.translate_api_key)
    return NullProvider()


@lru_cache
def get_translation_service() -> TranslationService:
    """App-scoped service so the circuit breaker persists across requests."""
    return TranslationService(get_translation_provider())


async def to_english_cached(
    session: AsyncSession,
    service: TranslationService,
    *,
    display_name: str,
    source_lang: str,
) -> TranslationOutcome:
    """Translate to English via the persistent cache, so we never pay twice.

    English input and degraded (needs_review) results are not cached — only
    confirmed non-English translations.
    """
    from app.repositories.translation_cache import TranslationCacheRepository

    if source_lang.split("-")[0] == "en":
        return await service.to_english(display_name=display_name, source_lang=source_lang)

    repo = TranslationCacheRepository(session)
    cached = await repo.get(display_name, source_lang, "en")
    if cached is not None:
        return TranslationOutcome(
            canonical_en=cached.result, romanization=cached.romanization, needs_review=False
        )

    outcome = await service.to_english(display_name=display_name, source_lang=source_lang)
    if not outcome.needs_review:
        await repo.put(
            source_text=display_name,
            source_lang=source_lang,
            target_lang="en",
            result=outcome.canonical_en,
            romanization=outcome.romanization,
            provider=service.provider.name,
        )
    return outcome
