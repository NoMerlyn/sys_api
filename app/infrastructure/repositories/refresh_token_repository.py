"""SQLAlchemy implementation of RefreshTokenRepository."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.common.interfaces.refresh_token_repository import (
    RefreshTokenRepository,
)
from app.infrastructure.db.models.refresh_token import RefreshToken


class SqlRefreshTokenRepository(RefreshTokenRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(
        self,
        *,
        token: str,
        user_id: int,
        expires_at: datetime,
        user_agent: str | None = None,
        ip_address: str | None = None,
    ) -> None:
        row = RefreshToken(
            token=token,
            user_id=user_id,
            expires_at=expires_at,
            user_agent=user_agent,
            ip_address=ip_address,
        )
        self._session.add(row)
        await self._session.flush()

    async def find_active(self, token: str) -> dict | None:
        stmt = select(RefreshToken).where(
            RefreshToken.token == token,
            RefreshToken.revoked_at.is_(None),
            RefreshToken.expires_at > func.now(),
        )
        row = (await self._session.execute(stmt)).scalar_one_or_none()
        if row is None:
            return None
        return {
            "id": row.id,
            "token": row.token,
            "user_id": row.user_id,
            "expires_at": row.expires_at,
        }

    async def revoke(self, token: str) -> None:
        await self._session.execute(
            update(RefreshToken)
            .where(RefreshToken.token == token, RefreshToken.revoked_at.is_(None))
            .values(revoked_at=func.now())
        )
        await self._session.flush()

    async def revoke_all_for_user(self, user_id: int) -> int:
        from sqlalchemy import func, select

        # Count first so we can return the number of revoked tokens
        # even though SQLAlchemy 2.x async Result has no rowcount.
        count_stmt = (
            select(func.count())
            .select_from(RefreshToken)
            .where(
                RefreshToken.user_id == user_id,
                RefreshToken.revoked_at.is_(None),
            )
        )
        count = (await self._session.execute(count_stmt)).scalar_one()
        await self._session.execute(
            update(RefreshToken)
            .where(RefreshToken.user_id == user_id, RefreshToken.revoked_at.is_(None))
            .values(revoked_at=func.now())
        )
        await self._session.flush()
        return int(count)
