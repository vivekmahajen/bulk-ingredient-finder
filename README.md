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

## API surface (PR-0)

| Method & path        | Purpose                                             |
| -------------------- | --------------------------------------------------- |
| `GET /healthz`       | Liveness probe (200 JSON)                            |
| `GET /readyz`        | Readiness probe (checks DB; 200 or 503)             |
| `GET /api/v1/ping`   | Versioned API liveness ping                          |
| `GET /docs`          | Swagger UI                                           |

Errors are returned as RFC-7807 `application/problem+json`. Logs are structured
JSON (structlog) outside `development`.

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
