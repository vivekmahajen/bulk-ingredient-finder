# Rasoi Radar API — deterministic container image.
#
# The repo root is a pnpm/Node monorepo, so Railway's auto-detection tries to
# build the web app there. Set the Railway service's Root Directory to
# `apps/api` and it will build this Dockerfile instead.
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Install the API and its dependencies. asyncpg/argon2-cffi ship manylinux
# wheels, so no compiler toolchain is needed on the slim base.
COPY pyproject.toml ./
COPY app ./app
COPY alembic ./alembic
COPY alembic.ini ./
RUN pip install --upgrade pip && pip install .

# Railway injects $PORT. Apply migrations, then serve.
EXPOSE 8000
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
