"""FastAPI application factory for Rasoi Radar."""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from slowapi.errors import RateLimitExceeded
from starlette.middleware.base import RequestResponseEndpoint
from starlette.responses import Response

from app.api.v1 import api_router
from app.api.v1.health import router as health_router
from app.core.config import settings
from app.core.cookies import CSRF_COOKIE, CSRF_HEADER
from app.core.errors import _problem_response, register_exception_handlers
from app.core.limiter import limiter
from app.core.logging import configure_logging, get_logger
from app.core.security import constant_time_equals

logger = get_logger("app")

# Mutating requests are CSRF-protected via double-submit once a session exists.
# Login/register/refresh/logout/accept establish or clear the session themselves.
_CSRF_EXEMPT_PREFIXES = ("/api/v1/auth/",)
_MUTATING_METHODS = {"POST", "PUT", "PATCH", "DELETE"}


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

    # CORS — the exact origin list plus a regex (Vercel preview URLs by default);
    # an origin is allowed if it matches either.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_origin_regex=settings.cors_origin_regex_or_none,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # CSRF double-submit for mutating requests (only once a session cookie exists).
    @app.middleware("http")
    async def _csrf_middleware(request: Request, call_next: RequestResponseEndpoint) -> Response:
        if request.method in _MUTATING_METHODS and not request.url.path.startswith(
            _CSRF_EXEMPT_PREFIXES
        ):
            csrf_cookie = request.cookies.get(CSRF_COOKIE)
            if csrf_cookie:
                header = request.headers.get(CSRF_HEADER)
                if not header or not constant_time_equals(header, csrf_cookie):
                    return _problem_response(
                        status_code=403,
                        title="CSRF check failed",
                        detail="Missing or invalid CSRF token.",
                        instance=str(request.url.path),
                    )
        return await call_next(request)

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


def _rate_limit_handler(request: Request, exc: Exception) -> Response:
    return _problem_response(
        status_code=429,
        title="Too Many Requests",
        detail="Rate limit exceeded. Please retry later.",
        instance=str(request.url.path),
    )


app = create_app()
