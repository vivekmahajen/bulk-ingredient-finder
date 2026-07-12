"""Translation cache — global (not org-scoped); never pay for a translation twice."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, UUIDPrimaryKeyMixin


class TranslationCache(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "translation_cache"
    __table_args__ = (
        UniqueConstraint("source_text", "source_lang", "target_lang", name="uq_translation_cache"),
    )

    source_text: Mapped[str] = mapped_column(Text, nullable=False)
    source_lang: Mapped[str] = mapped_column(Text, nullable=False)
    target_lang: Mapped[str] = mapped_column(Text, nullable=False)
    result: Mapped[str] = mapped_column(Text, nullable=False)
    romanization: Mapped[str | None] = mapped_column(Text, nullable=True)
    provider: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now(), nullable=False)
