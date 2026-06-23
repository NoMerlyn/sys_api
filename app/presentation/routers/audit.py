"""Admin-only audit log read endpoint."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.application.audit import (
    GetAuditLogsHandler,
    GetAuditLogsQuery,
)
from app.application.common.interfaces.audit_log_repository import (
    AuditLogRepository,
)
from app.core.deps import require_admin
from app.core.pagination import PaginatedResponse
from app.infrastructure.repositories.audit_log_repository import (
    SqlAuditLogRepository,
)

router = APIRouter(prefix="/audit-logs", tags=["audit"])


def _audit_repo() -> AuditLogRepository:
    # The handler will re-instantiate this on the right session, but
    # FastAPI's Depends machinery needs something to inject.
    return SqlAuditLogRepository.__new__(SqlAuditLogRepository)  # type: ignore[abstract]


@router.get("", response_model=PaginatedResponse)
async def list_audit_logs(
    _admin: Annotated[object, Depends(require_admin)],
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=200),
    action: str | None = None,
    entity: str | None = None,
    user_id: int | None = None,
    since: datetime | None = None,
) -> PaginatedResponse:
    repo = SqlAuditLogRepository.__new__(SqlAuditLogRepository)  # type: ignore[abstract]
    handler = GetAuditLogsHandler(repo)
    rows, total = await handler.handle(
        GetAuditLogsQuery(
            page=page,
            limit=limit,
            action=action,
            entity=entity,
            user_id=user_id,
            since=since,
        )
    )
    return PaginatedResponse(
        data=rows,
        page=page,
        limit=limit,
        total=total,
    )