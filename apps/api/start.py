"""Container entrypoint: apply DB migrations, then serve the API.

Railpack (Railway's builder) installs dependencies into a venv but doesn't
reliably expose the console scripts (``uvicorn``/``alembic``) on PATH, and the
installed Alembic has no ``__main__`` module, so neither the bare commands nor
``python -m alembic`` work there. Driving both through their Python APIs from a
single script sidesteps all of that — it only needs the interpreter that has the
dependencies installed.

Run with: ``python start.py``
"""

from __future__ import annotations

import os

import uvicorn
from alembic import command
from alembic.config import Config


def main() -> None:
    # alembic.ini lives next to this file (the app root); env.py supplies the
    # database URL and TLS connect args from application settings.
    command.upgrade(Config("alembic.ini"), "head")

    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=int(os.environ.get("PORT", "8080")),
    )


if __name__ == "__main__":
    main()
