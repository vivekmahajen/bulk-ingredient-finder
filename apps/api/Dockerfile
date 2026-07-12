# Rasoi Radar API image. Built with the build context = this directory
# (apps/api), which is the Railway service's Root Directory. COPY paths are
# therefore relative to apps/api (no prefix).
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# asyncpg/argon2-cffi ship manylinux wheels — no compiler toolchain needed.
COPY pyproject.toml ./
COPY app ./app
COPY alembic ./alembic
COPY alembic.ini ./
COPY start.py ./
RUN pip install --upgrade pip && pip install .

# start.py runs migrations (alembic API) then serves uvicorn on $PORT.
EXPOSE 8080
CMD ["python", "start.py"]
