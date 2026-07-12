"""Translation-cache repository (global cache; not org-scoped)."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.translation_cache import TranslationCache


class TranslationCacheRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get(
        self, source_text: str, source_lang: str, target_lang: str
    ) -> TranslationCache | None:
        stmt = select(TranslationCache).where(
            TranslationCache.source_text == source_text,
            TranslationCache.source_lang == source_lang,
            TranslationCache.target_lang == target_lang,
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def put(
        self,
        *,
        source_text: str,
        source_lang: str,
        target_lang: str,
        result: str,
        romanization: str | None,
        provider: str,
    ) -> None:
        # Upsert on the unique triple — concurrent writers don't error.
        stmt = (
            insert(TranslationCache)
            .values(
                source_text=source_text,
                source_lang=source_lang,
                target_lang=target_lang,
                result=result,
                romanization=romanization,
                provider=provider,
            )
            .on_conflict_do_nothing(constraint="uq_translation_cache")
        )
        await self.session.execute(stmt)
