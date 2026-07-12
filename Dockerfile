# Rasoi Radar API — deterministic container image, built from the REPO ROOT so
# Railway needs no "Root Directory" configuration (it auto-uses a root
# Dockerfile). The web app deploys separately on Vercel and ignores this file.
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Build context is the repo root, so paths are prefixed with apps/api/.
# asyncpg/argon2-cffi ship manylinux wheels — no compiler toolchain needed.
COPY apps/api/pyproject.toml ./
COPY apps/api/app ./app
COPY apps/api/alembic ./alembic
COPY apps/api/alembic.ini ./
RUN pip install --upgrade pip && pip install .

# Railway injects $PORT. Apply migrations, then serve.
EXPOSE 8000
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
