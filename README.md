# Rasoi Radar

Restaurant bulk-ingredient **price intelligence** — a multilingual ingredient
catalog with store- and purchase-frequency-aware price search. Built to help
restaurants (dogfooded first on **Hari Om**) find the best bulk prices across
broadline, cash-and-carry, and ethnic-wholesale suppliers.

> **Status:** PR-0 — scaffold & infrastructure. Auth (PR-1) and the domain model
> (PR-2) build on top of this.

## Stack

| Layer     | Tech                                                              |
| --------- | ---------------------------------------------------------------- |
| Web       | Next.js 15 (App Router, TypeScript strict), Tailwind, shadcn/ui  |
| API       | FastAPI (Python 3.12), SQLAlchemy 2.0 async + asyncpg, Alembic   |
| Database  | PostgreSQL 16 (`pg_trgm`, `unaccent`, `cube`, `earthdistance`)   |
| Shared    | zod ⇄ Pydantic mirrored from `packages/shared/schema.json`       |
| Hosting   | Web → Vercel · API + DB → Railway                                |

## Monorepo layout

```
apps/web/          Next.js 15 front-end (@rasoi/web)
apps/api/          FastAPI back-end (create_app() factory, routers under /api/v1)
packages/shared/   Cross-language constants/enums (@rasoi/shared) — schema.json is source of truth
```

## Local setup (≤ 10 steps)

Prerequisites: **Node ≥ 20 + pnpm 10**, **Python 3.12**, **PostgreSQL 16**.

1. Clone the repo and `cd` into it.
2. Create the database: `createdb rasoi_radar`.
3. Copy env files: `cp apps/api/.env.example apps/api/.env` and `cp apps/web/.env.example apps/web/.env.local`.
4. Edit `apps/api/.env` so `DATABASE_URL` points at your local Postgres.
5. Install everything: `make install` (pnpm workspaces + a Python venv under `apps/api/.venv`).
6. Apply migrations (enables the Postgres extensions): `make migrate`.
7. Seed baseline data: `make seed` (idempotent; a no-op placeholder until PR-2).
8. Start both apps: `make dev` → web on http://localhost:3000, api on http://localhost:8000.
9. Verify the API: `curl http://localhost:8000/healthz` → `{"status":"ok",...}`.
10. Run the test suites: `make test`.

## Make targets

| Target           | What it does                                        |
| ---------------- | --------------------------------------------------- |
| `make install`   | Install web + api dependencies                      |
| `make dev`       | Run web (:3000) and api (:8000) together            |
| `make test`      | Run pytest + vitest                                 |
| `make lint`      | eslint (web) + ruff (api)                            |
| `make typecheck` | tsc (web) + mypy (api)                               |
| `make migrate`   | Apply Alembic migrations to head                    |
| `make migration m="msg"` | Autogenerate a new migration                |
| `make seed`      | Seed the database (idempotent)                      |

## API surface

| Method & path                 | Purpose                                         |
| ----------------------------- | ----------------------------------------------- |
| `GET /healthz`                | Liveness probe (200 JSON)                        |
| `GET /readyz`                 | Readiness probe (checks DB; 200 or 503)         |
| `GET /api/v1/ping`            | Versioned API liveness ping                      |
| `GET /api/v1/ingredients`     | List active ingredients (org-scoped) — PR-2      |
| `POST /api/v1/ingredients`    | Add ingredient (detect/translate/aliases) — PR-3 |
| `GET /api/v1/ingredients/{id}`| Ingredient + aliases — PR-2                       |
| `POST /api/v1/ingredients/{id}/aliases` | Add a user alias (correction) — PR-3   |
| `DELETE …/aliases/{alias_id}` | Remove an alias (correction) — PR-3              |
| `GET /api/v1/search/ingredients` | Multilingual search (trigram + translation) — PR-4 |
| `GET /api/v1/stores`          | List stores; `?near=lat,lng&radius_km=` — PR-2/5 |
| `POST /api/v1/stores`         | Add store (geocodes the address) — PR-5          |
| `PATCH /api/v1/stores/{id}`   | Update store (re-geocodes) — PR-5                |
| `DELETE /api/v1/stores/{id}`  | Soft-delete store — PR-5                          |
| `GET /api/v1/stores/{id}/prices` | Latest price per ingredient at a store — PR-5 |
| `GET /api/v1/stores/{id}/wins`| Ingredients this store wins on — PR-5            |
| `GET`/`PATCH /api/v1/org`     | Read / set org home location (geocoded) — PR-5   |
| `POST /api/v1/prices`         | Log a price (normalized + unit/category warnings) — PR-6 |
| `POST /api/v1/prices/bulk`    | Bulk log ≤200 (207 per-row results) — PR-6      |
| `GET /api/v1/prices`          | List prices (paginated, filterable) — PR-6      |
| `GET /api/v1/ingredients/{id}/price-history` | Per-store time series — PR-6     |
| `GET /docs`                   | Swagger UI                                        |

Errors are returned as RFC-7807 `application/problem+json`. Logs are structured
JSON (structlog) outside `development`.

## Domain model (PR-2)

Org-scoped catalog + pricing schema (migration `0002`). Every domain table carries
`org_id`; **all** queries flow through `app/repositories/` so tenant isolation is
never skipped (guarded by `tests/test_org_scoping.py`).

- **ingredients** + **ingredient_aliases** — the multilingual catalog. Each alias
  (`translation` / `transliteration` / `synonym` / `user_alias`) is trigram- and
  `unaccent`-indexed so search finds an ingredient regardless of language/spelling.
- **stores** — suppliers with kind, geo (`lat`/`lng`, earthdistance-indexed),
  delivery days, min order.
- **price_entries** — normalized to price per base unit via three STORED generated
  columns (`unit_price_cents_per_kg` / `_per_l` / `_per_each`). Conversion factors
  are the single source in `packages/shared/src/units.ts` and `apps/api/app/units.py`
  (property-tested with hypothesis; the TS mirror is covered by vitest).
- **orgs** / **users** / **audit_log** — the minimal tenancy + attribution substrate
  that PR-1 auth extends.

`make seed` idempotently loads the **Hari Om** dogfood org, an owner user, the 29
starter ingredients (frequencies per the forecast rule: staples monthly,
dairy/protein twice-weekly, produce weekly), and 6 starter stores.

## CI & deploy previews

GitHub Actions (`.github/workflows/ci.yml`) runs on every PR:

- **Web:** `pnpm lint` → `pnpm typecheck` → `vitest`.
- **API:** `ruff` → `mypy` → `alembic upgrade head` (against a Postgres 16 service) → `pytest`.

**Deploy previews:** connect the repo to Vercel with the project root set to
`apps/web`. Vercel builds a preview deployment for every PR and comments the
preview URL on the pull request. Point the preview's `NEXT_PUBLIC_API_URL` at the
corresponding Railway API deployment.

## Environment variables

Every variable is documented inline in `apps/api/.env.example` and
`apps/web/.env.example`. Highlights: `DATABASE_URL`, `JWT_SECRET`,
`JWT_REFRESH_SECRET`, `TRANSLATE_PROVIDER`/`TRANSLATE_API_KEY`,
`GEOCODE_PROVIDER`/`GEOCODE_API_KEY`, `NEXT_PUBLIC_API_URL`, and `MULTI_TENANT`
(ships `false` — single-restaurant dogfood mode).
