"""Add-ingredient pipeline: detect → translate → transliterate → synonyms.

Language handling is first-class:
  * ``source_lang`` omitted → detect it; ambiguous non-English (confidence < 0.7)
    raises :class:`LanguageAmbiguous` so the UI can ask which language it is.
  * non-English source → translate to an English ``canonical_name_en`` and, for
    non-Latin scripts, capture a transliteration.
  * curated dictionary synonyms are attached so the item is findable by any of its
    common names.

Translation never blocks creation — a provider outage yields
``canonical = display_name`` with ``needs_review = True`` (handled in
``TranslationService.to_english``).
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.deps import RequestContext
from app.models.enums import AliasKind
from app.models.ingredient import FORECAST_MONTHS, Ingredient, IngredientAlias, IngredientForecast
from app.schemas.ingredient import IngredientCreate
from app.services import audit
from app.services.translation import TranslationService, to_english_cached
from app.synonyms import find_group

CONFIDENCE_THRESHOLD = 0.7


class LanguageAmbiguous(Exception):
    """Raised when detection can't confidently pick a non-English language."""

    def __init__(self, detected: str, candidates: list[str]) -> None:
        self.detected = detected
        self.candidates = candidates
        super().__init__(f"ambiguous language: {detected}")


def _base_lang(lang: str) -> str:
    return lang.split("-")[0]


async def add_ingredient(
    session: AsyncSession,
    ctx: RequestContext,
    payload: IngredientCreate,
    translation: TranslationService,
) -> Ingredient:
    display_name = payload.display_name.strip()

    # 1. Resolve source language.
    source_lang = payload.source_lang
    if not source_lang:
        detection = await translation.detect(display_name)
        if detection.lang != "en" and detection.confidence < CONFIDENCE_THRESHOLD:
            raise LanguageAmbiguous(detection.lang, detection.candidates)
        source_lang = detection.lang

    # 2. Normalize to an English canonical name (+ transliteration), via the cache.
    outcome = await to_english_cached(
        session, translation, display_name=display_name, source_lang=source_lang
    )

    ingredient = Ingredient(
        org_id=ctx.org_id,
        canonical_name_en=outcome.canonical_en,
        display_name=display_name,
        source_lang=source_lang,
        category=payload.category,
        default_unit=payload.default_unit,
        purchase_frequency=payload.purchase_frequency,
        par_level=payload.par_level,
        notes=payload.notes,
        needs_review=outcome.needs_review,
        created_by=ctx.user_id,
    )
    session.add(ingredient)
    await session.flush()

    # 3. Build aliases, de-duplicated case-insensitively by (alias, lang).
    seen: set[tuple[str, str]] = set()

    def add_alias(alias: str, lang: str, kind: AliasKind) -> None:
        alias = alias.strip()
        if not alias:
            return
        key = (alias.lower(), lang.lower())
        if key in seen:
            return
        seen.add(key)
        session.add(
            IngredientAlias(
                org_id=ctx.org_id,
                ingredient_id=ingredient.id,
                alias=alias,
                lang=lang,
                kind=kind,
            )
        )

    if _base_lang(source_lang) != "en":
        add_alias(display_name, source_lang, AliasKind.TRANSLATION)
    if outcome.romanization:
        add_alias(
            outcome.romanization, f"{_base_lang(source_lang)}-Latn", AliasKind.TRANSLITERATION
        )
    add_alias(outcome.canonical_en, "en", AliasKind.TRANSLATION)

    # 4. Curated dictionary synonyms (match on canonical, the typed term, or romanization).
    group = (
        find_group(outcome.canonical_en)
        or find_group(display_name)
        or (find_group(outcome.romanization) if outcome.romanization else None)
    )
    if group is not None:
        add_alias(group.canonical_en, "en", AliasKind.SYNONYM)
        for term in group.terms:
            add_alias(term.alias, term.lang, AliasKind.SYNONYM)

    # 5. Optional demand forecast + sourcing (monthly amounts, serving, vendor).
    if payload.forecast is not None:
        f = payload.forecast
        forecast = IngredientForecast(
            org_id=ctx.org_id,
            ingredient_id=ingredient.id,
            annual=f.annual,
            g_ml_per_serving=f.g_ml_per_serving,
            recommended_vendor=f.recommended_vendor,
            vendor_website=f.vendor_website,
        )
        for month in FORECAST_MONTHS:
            setattr(forecast, month, getattr(f, month))
        session.add(forecast)

    audit.record(
        session,
        org_id=ctx.org_id,
        user_id=ctx.user_id,
        action="ingredient.create",
        entity="ingredient",
        entity_id=ingredient.id,
        meta={
            "display_name": display_name,
            "source_lang": source_lang,
            "needs_review": outcome.needs_review,
        },
    )

    await session.flush()
    return ingredient
