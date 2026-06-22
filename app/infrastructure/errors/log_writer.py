"""Error log writer (called from the global exception handler)."""

from __future__ import annotations

import logging
import traceback
from typing import Any

from app.infrastructure.db.models.error_log import ErrorLog

logger = logging.getLogger(__name__)


def build_error_log(
    *,
    message: str,
    exception: BaseException | None,
    path: str,
    user_id: int | None = None,
    source: str | None = None,
) -> ErrorLog:
    return ErrorLog(
        message=message,
        stack_trace="".join(
            traceback.format_exception(type(exception), exception, exception.__traceback__)
        )
        if exception
        else None,
        exception_type=type(exception).__name__ if exception else None,
        user_id=user_id,
        path=path,
        source=source,
    )


async def persist_error_log(session: Any, log: ErrorLog) -> None:
    session.add(log)
    await session.flush()
    logger.info("Persisted ErrorLog id=%s", getattr(log, "id", None))
