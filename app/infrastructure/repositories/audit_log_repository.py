"""SQLAlchemy implementation of AuditLogRepository."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.common.interfaces.audit_log_repository import (
    AuditLogRepository,
)
from app.infrastructure.db.models.audit_log import AuditLog


class SqlAuditLogRepository(AuditLogRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(
        self,
        *,
        action: str,
        entity: str,
        entity_id: int | None = None,
        user_id: int | None = None,
        detail: str | None = None,
        ip_address: str | None = None,
    ) -> None:
        row = AuditLog(
            action=action,
            entity=entity,
            entity_id=entity_id,
            user_id=user_id,
            detail=detail,
            ip_address=ip_address,
        )
        self._session.add(row)
        await self._session.flush()

    async def list(
        self,
        *,
        page: int,
        limit: int,
        action: str | None = None,
        entity: str | None = None,
        user_id: int | None = None,
        since: datetime | None = None,
    ) -> tuple[list[dict], int]:
        stmt = select(AuditLog)
        count_stmt = select(func.count()).select_from(AuditLog)
        where = []
        if action:
            where.append(AuditLog.action == action)
        if entity:
            where.append(AuditLog.entity == entity)
        if user_id is not None:
            where.append(AuditLog.user_id == user_id)
        if since:
            where.append(AuditLog.created_at >= since)
        if where:
            stmt = stmt.where(and_(*where))
            count_stmt = count_stmt.where(and_(*where))
        offset = max(0, (page - 1) * limit)
        stmt = stmt.order_by(AuditLog.id.desc()).offset(offset).limit(limit)
        rows = (await self._session.execute(stmt)).scalars().all()
        total = (await self._session.execute(count_stmt)).scalar_one()
        return (
            [
                {
                    "id": r.id,
                    "action": r.action,
                    "entity": r.entity,
                    "entity_id": r.entity_id,
                    "user_id": r.user_id,
                    "detail": r.detail,
                    "ip_address": r.ip_address,
                    "created_at": r.created_at,
                }
                for r in rows
            ],
            total,
        )