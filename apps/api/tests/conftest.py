"""Pytest fixtures: isolated Postgres test DB, sessions, and an app client.

The domain relies on Postgres-only features (trigram/unaccent indexes,
earthdistance, STORED generated columns), so tests run against a real Postgres
database — ``rasoi_radar_test`` by default, overridable via ``TEST_DATABASE_URL``.
Migrations are applied once per session; tables are truncated between tests.
"""

from __future__ import annotations

import os
import subprocess
import sys
from collections.abc import AsyncGenerator

import asyncpg
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql+asyncpg://postgres:postgres@localhost:5432/rasoi_radar_test",
)

_ASYNCPG_ADMIN = "postgresql://postgres:postgres@localhost:5432/postgres"
_DB_NAME = TEST_DATABASE_URL.rsplit("/", 1)[-1]

DOMAIN_TABLES = [
    "price_entries",
    "ingredient_aliases",
    "ingredients",
    "stores",
    "audit_log",
    "users",
    "orgs",
]


async def _ensure_database() -> None:
    conn = await asyncpg.connect(_ASYNCPG_ADMIN)
    try:
        exists = await conn.fetchval("SELECT 1 FROM pg_database WHERE datname = $1", _DB_NAME)
        if not exists:
            await conn.execute(f'CREATE DATABASE "{_DB_NAME}"')
    finally:
        await conn.close()


@pytest_asyncio.fixture(scope="session", autouse=True)
async def _migrated_db() -> AsyncGenerator[None, None]:
    await _ensure_database()
    env = {**os.environ, "DATABASE_URL": TEST_DATABASE_URL}
    subprocess.run([sys.executable, "-m", "alembic", "upgrade", "head"], check=True, env=env)
    yield


@pytest_asyncio.fixture()
async def db_engine():
    engine = create_async_engine(TEST_DATABASE_URL, poolclass=None)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture()
async def db_session(db_engine) -> AsyncGenerator[AsyncSession, None]:
    factory = async_sessionmaker(bind=db_engine, expire_on_commit=False, autoflush=False)
    async with db_engine.begin() as conn:
        await conn.exec_driver_sql(f"TRUNCATE {', '.join(DOMAIN_TABLES)} RESTART IDENTITY CASCADE")
    async with factory() as session:
        yield session


@pytest_asyncio.fixture()
async def client(db_engine) -> AsyncGenerator[AsyncClient, None]:
    """An in-loop async client whose DB session is bound to the test engine.

    Uses ``ASGITransport`` (not ``TestClient``) so the app runs in the same event
    loop as the test — required for the shared asyncpg engine to work.
    """
    from app.db.session import get_session
    from app.main import create_app

    factory = async_sessionmaker(bind=db_engine, expire_on_commit=False, autoflush=False)

    async def _override_get_session() -> AsyncGenerator[AsyncSession, None]:
        async with factory() as session:
            yield session

    app = create_app()
    app.dependency_overrides[get_session] = _override_get_session
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()
