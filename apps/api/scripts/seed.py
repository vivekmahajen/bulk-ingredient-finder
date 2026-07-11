"""Database seed entrypoint (`make seed`).

PR-0 scaffold: this is a no-op placeholder that verifies connectivity. The real
seed — the single "Hari Om" org (dogfood mode), 29 ingredients, and 6 starter
stores — lands in PR-2 alongside the domain model.
"""

from __future__ import annotations

import asyncio

from sqlalchemy import text

from app.core.logging import configure_logging, get_logger
from app.db.session import async_session_factory, engine


async def seed() -> None:
    configure_logging()
    logger = get_logger("seed")
    async with async_session_factory() as session:
        await session.execute(text("SELECT 1"))
    await engine.dispose()
    logger.info("seed_complete", note="PR-0 placeholder — domain seed lands in PR-2")


if __name__ == "__main__":
    asyncio.run(seed())
