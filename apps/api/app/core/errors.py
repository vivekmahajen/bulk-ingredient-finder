"""RFC-7807 problem+json error handling.

Registers exception handlers that render every error as ``application/problem+json``
per RFC 7807, so clients get a consistent, machine-readable error envelope.
"""

from __future__ import annotations

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.logging import get_logger

logger = get_logger("errors")

PROBLEM_CONTENT_TYPE = "application/problem+json"


class ProblemException(Exception):
    """Raise to return a fully-specified RFC-7807 problem response."""

    def __init__(
        self,
        *,
        status_code: int,
        title: str,
        detail: str | None = None,
        type_: str = "about:blank",
        instance: str | None = None,
    ) -> None:
        self.status_code = status_code
        self.title = title
        self.detail = detail
        self.type_ = type_
        self.instance = instance
        super().__init__(detail or title)


def _problem_response(
    *,
    status_code: int,
    title: str,
    detail: str | None,
    instance: str | None,
    type_: str = "about:blank",
    extra: dict[str, object] | None = None,
) -> JSONResponse:
    body: dict[str, object] = {"type": type_, "title": title, "status": status_code}
    if detail is not None:
        body["detail"] = detail
    if instance is not None:
        body["instance"] = instance
    if extra:
        body.update(extra)
    return JSONResponse(
        status_code=status_code,
        content=body,
        media_type=PROBLEM_CONTENT_TYPE,
    )


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(ProblemException)
    async def _handle_problem(request: Request, exc: ProblemException) -> JSONResponse:
        return _problem_response(
            status_code=exc.status_code,
            title=exc.title,
            detail=exc.detail,
            instance=exc.instance or str(request.url.path),
            type_=exc.type_,
        )

    @app.exception_handler(StarletteHTTPException)
    async def _handle_http(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        title = getattr(exc, "detail", None) or "HTTP Error"
        return _problem_response(
            status_code=exc.status_code,
            title=str(title),
            detail=None,
            instance=str(request.url.path),
        )

    @app.exception_handler(RequestValidationError)
    async def _handle_validation(request: Request, exc: RequestValidationError) -> JSONResponse:
        return _problem_response(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            title="Validation Error",
            detail="One or more fields failed validation.",
            instance=str(request.url.path),
            extra={"errors": exc.errors()},
        )

    @app.exception_handler(Exception)
    async def _handle_unexpected(request: Request, exc: Exception) -> JSONResponse:
        logger.error("unhandled_exception", path=str(request.url.path), exc_info=exc)
        return _problem_response(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            title="Internal Server Error",
            detail="An unexpected error occurred.",
            instance=str(request.url.path),
        )
