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


import traceback
import json


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


async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("Unhandled Exception: %s", str(exc))
    
    user_id = None
    auth_header = request.headers.get("authorization")
    if auth_header and auth_header.lower().startswith("bearer "):
        token = auth_header[7:].strip()
        try:
            from app.config import get_settings
            from app.core.security import decode_access_token
            settings = get_settings()
            payload = decode_access_token(
                token,
                secret=settings.jwt_secret,
                issuer=settings.jwt_issuer,
                audience=settings.jwt_audience,
                algorithm=settings.jwt_algorithm,
            )
            user_id = int(payload["sub"])
        except Exception:
            pass

    stack = traceback.format_exc()
    error_data = {
        "message": str(exc),
        "exception_type": exc.__class__.__name__,
        "path": request.url.path,
        "method": request.method,
        "query_params": dict(request.query_params),
    }

    try:
        from app.application.common.uow import uow
        from app.infrastructure.db.models.error_log import ErrorLog
        async with uow() as session:
            log = ErrorLog(
                message=json.dumps(error_data, ensure_ascii=False),
                stack_trace=stack,
                exception_type=exc.__class__.__name__,
                user_id=user_id,
                path=request.url.path,
                source="global_exception_handler"
            )
            session.add(log)
    except Exception as db_exc:
        logger.exception("Failed to persist error log: %s", db_exc)

    return JSONResponse(
        status_code=500,
        content={
            "code": "INTERNAL_SERVER_ERROR",
            "message": "Ocurrió un error interno en la plataforma.",
            "details": {"message": str(exc)}
        }
    )


def register_exception_handlers(app: FastAPI) -> None:
    """Alternative manual registration if create_app is bypassed."""
    app.add_exception_handler(AppError, app_error_handler)  # type: ignore[arg-type]
    app.add_exception_handler(BusinessError, business_exception_handler)  # type: ignore[arg-type]
    app.add_exception_handler(Exception, global_exception_handler)
