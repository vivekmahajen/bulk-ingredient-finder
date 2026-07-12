"""FastAPI application factory for Rasoi Radar."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi.errors import RateLimitExceeded

from app.api.v1 import api_router
from app.api.v1.health import router as health_router
from app.core.config import settings
from app.core.errors import register_exception_handlers
from app.core.limiter import limiter
from app.core.logging import configure_logging, get_logger

logger = get_logger("app")


def create_app() -> FastAPI:
    """Build and configure the FastAPI application."""
    configure_logging()

    app = FastAPI(
        title="Rasoi Radar API",
        version="0.0.0",
        description="Restaurant bulk-ingredient price intelligence.",
        docs_url="/docs",
        openapi_url="/openapi.json",
    )

    # Rate limiting (slowapi)
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_handler)

    # CORS — restricted to the Vercel domain(s) + localhost.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # RFC-7807 problem+json error handling.
    register_exception_handlers(app)

    # Root-level infra probes.
    app.include_router(health_router)

    # Versioned API surface.
    app.include_router(api_router, prefix="/api/v1")

    logger.info(
        "app_started",
        environment=settings.environment,
        multi_tenant=settings.multi_tenant,
        cors_origins=settings.cors_origin_list,
    )
    return app


def _rate_limit_handler(request, exc):  # type: ignore[no-untyped-def]
    from fastapi import status

    from app.core.errors import _problem_response

    return _problem_response(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        title="Too Many Requests",
        detail="Rate limit exceeded. Please retry later.",
        instance=str(request.url.path),
    )


app = create_app()
