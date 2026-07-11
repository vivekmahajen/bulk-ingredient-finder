"""Ingredient + IngredientAlias models — the multilingual catalog backbone."""

from __future__ import annotations

import uuid

from sqlalchemy import Boolean, ForeignKey, Numeric, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, OrgScopedMixin, TimestampMixin, UUIDPrimaryKeyMixin
from app.models._sa_enum import pg_enum
from app.models.enums import AliasKind, Category, DefaultUnit, PurchaseFrequency


class Ingredient(UUIDPrimaryKeyMixin, OrgScopedMixin, TimestampMixin, Base):
    __tablename__ = "ingredients"

    canonical_name_en: Mapped[str] = mapped_column(Text, nullable=False)
    display_name: Mapped[str] = mapped_column(Text, nullable=False)
    source_lang: Mapped[str] = mapped_column(
        Text, nullable=False, default="en", server_default="en"
    )
    category: Mapped[Category] = mapped_column(pg_enum(Category, "category"), nullable=False)
    default_unit: Mapped[DefaultUnit] = mapped_column(
        pg_enum(DefaultUnit, "default_unit"), nullable=False
    )
    purchase_frequency: Mapped[PurchaseFrequency] = mapped_column(
        pg_enum(PurchaseFrequency, "purchase_frequency"),
        nullable=False,
        default=PurchaseFrequency.WEEKLY,
        server_default=PurchaseFrequency.WEEKLY.value,
    )
    par_level: Mapped[float | None] = mapped_column(Numeric, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
    )
    needs_review: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    aliases: Mapped[list[IngredientAlias]] = relationship(
        back_populates="ingredient",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class IngredientAlias(UUIDPrimaryKeyMixin, OrgScopedMixin, Base):
    __tablename__ = "ingredient_aliases"
    __table_args__ = (
        UniqueConstraint("ingredient_id", "alias", "lang", name="uq_alias_ingredient_alias_lang"),
    )

    ingredient_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("ingredients.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    alias: Mapped[str] = mapped_column(Text, nullable=False)
    lang: Mapped[str] = mapped_column(Text, nullable=False)
    kind: Mapped[AliasKind] = mapped_column(pg_enum(AliasKind, "alias_kind"), nullable=False)

    ingredient: Mapped[Ingredient] = relationship(back_populates="aliases")
