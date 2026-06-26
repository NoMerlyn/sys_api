"""Audit log use cases.

`LogActionCommand` is a write-only side effect called from other
handlers (login, create invoice, cancel invoice, etc.) so that the
audit trail captures what actually happened.

`GetAuditLogsQuery` is the read side: paginated, filterable listing
exposed to the admin UI.

`audit()` is a thin async-context helper used by routers to write a
row inside an existing session, without having to wire up the
handler.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.application.common.interfaces.audit_log_repository import (
    AuditLogRepository,
)
from app.infrastructure.repositories.audit_log_repository import (
    SqlAuditLogRepository,
)


@dataclass(frozen=True, slots=True)
class LogActionCommand:
    action: str
    entity: str
    entity_id: int | None = None
    user_id: int | None = None
    detail: str | None = None
    ip_address: str | None = None


@asynccontextmanager
async def audit(
    session: AsyncSession,
) -> AsyncIterator[AuditLogRepository]:
    """Yield a session-bound audit repo; the caller can call `.add(...)` on it.

    Usage:
        async with uow() as session:
            async with audit(session) as log:
                await log.add(action="...", entity="...")
    """
    yield SqlAuditLogRepository(session)


class LogActionHandler:
    """Kept for tests; production code uses the `audit()` context above."""

    def __init__(self, audit_repo: AuditLogRepository) -> None:
        self._audit = audit_repo

    async def handle(self, cmd: LogActionCommand) -> None:
        await self._audit.add(
            action=cmd.action,
            entity=cmd.entity,
            entity_id=cmd.entity_id,
            user_id=cmd.user_id,
            detail=cmd.detail,
            ip_address=cmd.ip_address,
        )


@dataclass(frozen=True, slots=True)
class GetAuditLogsQuery:
    page: int = 1
    limit: int = 50
    action: str | None = None
    entity: str | None = None
    user_id: int | None = None
    since: datetime | None = None


class GetAuditLogsHandler:
    def __init__(self, audit_repo: AuditLogRepository) -> None:
        self._audit = audit_repo

    async def handle(self, q: GetAuditLogsQuery) -> tuple[list[dict], int]:
        from app.application.common.uow import uow
        async with uow() as session:
            async with audit(session) as repo:
                return await repo.list(
                    page=q.page,
                    limit=q.limit,
                    action=q.action,
                    entity=q.entity,
                    user_id=q.user_id,
                    since=q.since,
                )
