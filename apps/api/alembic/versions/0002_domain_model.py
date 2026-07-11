"""domain model: orgs, users, audit, ingredients, aliases, stores, prices

Creates the PR-2 core schema:
  * native enum types
  * orgs / users / audit_log (minimal auth substrate)
  * ingredients / ingredient_aliases (multilingual catalog)
  * stores / price_entries (with STORED normalized unit-price columns)
  * trigram (unaccent) search indexes, org/frequency btree, earthdistance gist

Revision ID: 0002
Revises: 0001
Create Date: 2026-07-11 00:00:00.000000
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

ENUMS: dict[str, tuple[str, ...]] = {
    "role": ("owner", "manager", "staff"),
    "category": (
        "protein",
        "dairy",
        "produce",
        "staple",
        "spice",
        "frozen",
        "beverage",
        "packaging",
        "other",
    ),
    "default_unit": ("kg", "g", "l", "ml", "each", "case", "bag"),
    "purchase_frequency": (
        "daily",
        "twice_weekly",
        "weekly",
        "biweekly",
        "monthly",
        "quarterly",
    ),
    "alias_kind": ("translation", "transliteration", "synonym", "user_alias"),
    "store_kind": (
        "broadline",
        "cash_and_carry",
        "ethnic_wholesale",
        "produce_house",
        "retail",
        "online",
    ),
    "pack_unit": ("kg", "g", "lb", "oz", "l", "ml", "gal", "each"),
    "price_source": ("invoice", "shelf", "quote", "website", "manual"),
}

# NOTE: compare the enum column directly (``pack_unit = 'kg'``) rather than via a
# ``::text`` cast — the enum→text cast is only STABLE, which Postgres rejects in a
# generated-column expression ("generation expression is not immutable").
PER_KG = """CASE
  WHEN pack_unit = 'kg' THEN price_cents / (pack_qty * 1)
  WHEN pack_unit = 'g'  THEN price_cents / (pack_qty * 0.001)
  WHEN pack_unit = 'lb' THEN price_cents / (pack_qty * 0.45359237)
  WHEN pack_unit = 'oz' THEN price_cents / (pack_qty * 0.028349523)
  ELSE NULL END"""

PER_L = """CASE
  WHEN pack_unit = 'l'   THEN price_cents / (pack_qty * 1)
  WHEN pack_unit = 'ml'  THEN price_cents / (pack_qty * 0.001)
  WHEN pack_unit = 'gal' THEN price_cents / (pack_qty * 3.785411784)
  ELSE NULL END"""

PER_EACH = "CASE WHEN pack_unit = 'each' THEN price_cents / pack_qty ELSE NULL END"


def upgrade() -> None:
    # --- Enum types ---------------------------------------------------------
    for name, values in ENUMS.items():
        labels = ", ".join(f"'{v}'" for v in values)
        op.execute(f"CREATE TYPE {name} AS ENUM ({labels})")

    # --- Immutable unaccent wrapper (usable in expression indexes) ----------
    op.execute(
        """
        CREATE OR REPLACE FUNCTION f_unaccent(text) RETURNS text
        LANGUAGE sql IMMUTABLE PARALLEL SAFE STRICT AS
        $$ SELECT public.unaccent('public.unaccent', $1) $$;
        """
    )

    # --- Tables -------------------------------------------------------------
    op.execute(
        """
        CREATE TABLE orgs (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            name text NOT NULL,
            created_at timestamptz NOT NULL DEFAULT now(),
            updated_at timestamptz NOT NULL DEFAULT now()
        );
        """
    )
    op.execute(
        """
        CREATE TABLE users (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            org_id uuid NOT NULL REFERENCES orgs(id) ON DELETE CASCADE,
            email text NOT NULL UNIQUE,
            password_hash text,
            display_name text NOT NULL,
            locale text NOT NULL DEFAULT 'en',
            role role NOT NULL DEFAULT 'staff',
            is_active boolean NOT NULL DEFAULT true,
            created_at timestamptz NOT NULL DEFAULT now(),
            updated_at timestamptz NOT NULL DEFAULT now()
        )
        """
    )
    op.execute("CREATE INDEX ix_users_org_id ON users(org_id)")
    op.execute(
        """
        CREATE TABLE audit_log (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            org_id uuid NOT NULL REFERENCES orgs(id) ON DELETE CASCADE,
            user_id uuid REFERENCES users(id) ON DELETE SET NULL,
            action text NOT NULL,
            entity text NOT NULL,
            entity_id uuid,
            meta jsonb NOT NULL DEFAULT '{}',
            at timestamptz NOT NULL DEFAULT now()
        )
        """
    )
    op.execute("CREATE INDEX ix_audit_org_id ON audit_log(org_id)")
    op.execute(
        """
        CREATE TABLE ingredients (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            org_id uuid NOT NULL REFERENCES orgs(id) ON DELETE CASCADE,
            canonical_name_en text NOT NULL,
            display_name text NOT NULL,
            source_lang text NOT NULL DEFAULT 'en',
            category category NOT NULL,
            default_unit default_unit NOT NULL,
            purchase_frequency purchase_frequency NOT NULL DEFAULT 'weekly',
            par_level numeric,
            notes text,
            is_active boolean NOT NULL DEFAULT true,
            created_by uuid REFERENCES users(id) ON DELETE SET NULL,
            created_at timestamptz NOT NULL DEFAULT now(),
            updated_at timestamptz NOT NULL DEFAULT now()
        )
        """
    )
    op.execute("CREATE INDEX ix_ingredients_org_id ON ingredients(org_id)")
    op.execute(
        """
        CREATE TABLE ingredient_aliases (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            org_id uuid NOT NULL REFERENCES orgs(id) ON DELETE CASCADE,
            ingredient_id uuid NOT NULL REFERENCES ingredients(id) ON DELETE CASCADE,
            alias text NOT NULL,
            lang text NOT NULL,
            kind alias_kind NOT NULL,
            CONSTRAINT uq_alias_ingredient_alias_lang UNIQUE (ingredient_id, alias, lang)
        )
        """
    )
    op.execute("CREATE INDEX ix_aliases_org_id ON ingredient_aliases(org_id)")
    op.execute("CREATE INDEX ix_aliases_ingredient_id ON ingredient_aliases(ingredient_id)")
    op.execute(
        """
        CREATE TABLE stores (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            org_id uuid NOT NULL REFERENCES orgs(id) ON DELETE CASCADE,
            name text NOT NULL,
            kind store_kind NOT NULL,
            address_line text,
            city text,
            state text,
            postal text,
            lat numeric,
            lng numeric,
            website text,
            phone text,
            delivers boolean NOT NULL DEFAULT false,
            delivery_days text[],
            min_order numeric,
            notes text,
            is_active boolean NOT NULL DEFAULT true,
            created_at timestamptz NOT NULL DEFAULT now(),
            updated_at timestamptz NOT NULL DEFAULT now()
        )
        """
    )
    op.execute("CREATE INDEX ix_stores_org_id ON stores(org_id)")
    op.execute(
        f"""
        CREATE TABLE price_entries (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            org_id uuid NOT NULL REFERENCES orgs(id) ON DELETE CASCADE,
            ingredient_id uuid NOT NULL REFERENCES ingredients(id) ON DELETE CASCADE,
            store_id uuid NOT NULL REFERENCES stores(id) ON DELETE CASCADE,
            brand text,
            pack_desc text NOT NULL,
            pack_qty numeric NOT NULL,
            pack_unit pack_unit NOT NULL,
            price_cents integer NOT NULL,
            currency char(3) NOT NULL DEFAULT 'USD',
            observed_at date NOT NULL,
            source price_source NOT NULL,
            photo_url text,
            entered_by uuid REFERENCES users(id) ON DELETE SET NULL,
            created_at timestamptz NOT NULL DEFAULT now(),
            unit_price_cents_per_kg numeric GENERATED ALWAYS AS ({PER_KG}) STORED,
            unit_price_cents_per_l numeric GENERATED ALWAYS AS ({PER_L}) STORED,
            unit_price_cents_per_each numeric GENERATED ALWAYS AS ({PER_EACH}) STORED
        )
        """
    )
    op.execute("CREATE INDEX ix_price_org_id ON price_entries(org_id)")
    op.execute("CREATE INDEX ix_price_ingredient_id ON price_entries(ingredient_id)")
    op.execute("CREATE INDEX ix_price_store_id ON price_entries(store_id)")

    # --- Search / geo indexes ----------------------------------------------
    op.execute(
        "CREATE INDEX ix_ingredients_canonical_trgm ON ingredients "
        "USING gin (f_unaccent(lower(canonical_name_en)) gin_trgm_ops)"
    )
    op.execute(
        "CREATE INDEX ix_ingredients_display_trgm ON ingredients "
        "USING gin (f_unaccent(lower(display_name)) gin_trgm_ops)"
    )
    op.execute(
        "CREATE INDEX ix_aliases_alias_trgm ON ingredient_aliases "
        "USING gin (f_unaccent(lower(alias)) gin_trgm_ops)"
    )
    op.execute(
        "CREATE INDEX ix_ingredients_org_frequency ON ingredients (org_id, purchase_frequency)"
    )
    op.execute(
        "CREATE INDEX ix_stores_earthdistance ON stores "
        "USING gist (ll_to_earth(lat::float8, lng::float8))"
    )


def downgrade() -> None:
    for table in (
        "price_entries",
        "ingredient_aliases",
        "ingredients",
        "stores",
        "audit_log",
        "users",
        "orgs",
    ):
        op.execute(f"DROP TABLE IF EXISTS {table} CASCADE")

    op.execute("DROP FUNCTION IF EXISTS f_unaccent(text)")

    for name in reversed(list(ENUMS.keys())):
        op.execute(f"DROP TYPE IF EXISTS {name}")
