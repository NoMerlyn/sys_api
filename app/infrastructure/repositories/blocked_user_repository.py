"""SqlBlockedUserRepository (legacy parity)."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.common.interfaces.blocked_user_repository import IBlockedUserRepository
from app.infrastructure.db.models.blocked_user import BlockedUser


class SqlBlockedUserRepository(IBlockedUserRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def find_by_user_id(self, user_id: int) -> BlockedUser | None:
        result = await self._session.execute(
            select(BlockedUser).where(BlockedUser.user_id == user_id)
        )
        return result.scalar_one_or_none()

    async def upsert(  # type: ignore[override]
        self, user_id: int, failed_attempts: int, blocked_at: datetime | None
    ) -> BlockedUser:
        existing = await self.find_by_user_id(user_id)
        if existing is not None:
            existing.failed_attempts = failed_attempts
            existing.blocked_at = blocked_at
            await self._session.flush()
            return existing
        row = BlockedUser(
            user_id=user_id,
            failed_attempts=failed_attempts,
            blocked_at=blocked_at,
        )
        self._session.add(row)
        await self._session.flush()
        return row
