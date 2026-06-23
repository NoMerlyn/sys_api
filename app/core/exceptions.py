"""Application-level exceptions and FastAPI handlers.

Two-tier model:
- `AppError` is the base for every exception we own.
- `BusinessError` represents a rule violation (400/409).
- `NotFoundError` represents a missing entity (404).
- `AuthError` is reserved for L3 (auth router).
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)


class AppError(Exception):
    """Base for all application-owned exceptions."""

    code: str = "INTERNAL_ERROR"
    http_status: int = 500
    message: str = "Application error"

    def __init__(
        self,
        message: str | None = None,
        *,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message or self.message)
        if message is not None:
            self.message = message
        self.details = details or {}


class BusinessError(AppError):
    """A business rule was violated (validation, conflict, etc.)."""

    code = "BUSINESS_RULE_VIOLATION"
    http_status = 400


class NotFoundError(AppError):
    """The requested entity was not found."""

    code = "NOT_FOUND"
    http_status = 404


class AuthError(AppError):
    """Authentication failed or missing."""

    code = "UNAUTHORIZED"
    http_status = 401


class ForbiddenError(AppError):
    """The authenticated user lacks the required role."""

    code = "FORBIDDEN"
    http_status = 403


class ConflictError(AppError):
    """A state-machine or uniqueness conflict."""

    code = "CONFLICT"
    http_status = 409


class AccountBlockedError(AppError):
    """The user account is blocked after too many failed logins."""

    code = "ACCOUNT_BLOCKED"
    http_status = 423


async def app_error_handler(_: Request, exc: AppError) -> JSONResponse:
    logger.warning("AppError: %s — %s", exc.code, exc.message)
    return JSONResponse(
        status_code=exc.http_status,
        content={
            "code": exc.code,
            "message": exc.message,
            "details": exc.details,
        },
    )


async def business_exception_handler(_: Request, exc: BusinessError) -> JSONResponse:
    logger.info("BusinessError: %s — %s", exc.code, exc.message)
    return JSONResponse(
        status_code=exc.http_status,
        content={
            "code": exc.code,
            "message": exc.message,
            "details": exc.details,
        },
    )


def register_exception_handlers(app: FastAPI) -> None:
    """Alternative manual registration if create_app is bypassed."""
    app.add_exception_handler(AppError, app_error_handler)
    app.add_exception_handler(BusinessError, business_exception_handler)
