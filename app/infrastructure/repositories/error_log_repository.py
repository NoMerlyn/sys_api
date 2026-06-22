"""SqlErrorLogRepository."""

from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.common.interfaces.error_log_repository import IErrorLogRepository
from app.core.pagination import Page
from app.infrastructure.db.models.error_log import ErrorLog


class SqlErrorLogRepository(IErrorLogRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def find_all(
        self, page: Page, search: str | None = None
    ) -> tuple[Sequence[ErrorLog], int]:
        stmt = select(ErrorLog).order_by(ErrorLog.created_at.desc())
        count_stmt = select(func.count()).select_from(ErrorLog)
        if search:
            pattern = f"%{search}%"
            filt = or_(
                ErrorLog.message.ilike(pattern),
                ErrorLog.path.ilike(pattern),
                ErrorLog.exception_type.ilike(pattern),
            )
            stmt = stmt.where(filt)
            count_stmt = count_stmt.where(filt)
        stmt = stmt.offset(page.offset).limit(page.limit)
        rows = (await self._session.execute(stmt)).scalars().all()
        total = (await self._session.execute(count_stmt)).scalar_one()
        return list(rows), int(total)

    async def create(self, log: ErrorLog) -> ErrorLog:
        self._session.add(log)
        await self._session.flush()
        return log
