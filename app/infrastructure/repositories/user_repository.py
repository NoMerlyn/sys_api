"""SqlUserRepository — SQLAlchemy implementation of IUserRepository."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.common.interfaces.user_repository import IUserRepository
from app.core.pagination import Page
from app.infrastructure.db.models.user import User


class SqlUserRepository(IUserRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def find_by_id(self, user_id: int) -> User | None:
        result = await self._session.execute(select(User).where(User.id == user_id))
        return result.scalar_one_or_none()

    async def find_by_email(self, email: str) -> User | None:
        result = await self._session.execute(select(User).where(User.email == email))
        return result.scalar_one_or_none()

    async def find_by_username(self, username: str) -> User | None:
        result = await self._session.execute(select(User).where(User.username == username))
        return result.scalar_one_or_none()

    async def find_all(self, page: Page, search: str | None = None) -> tuple[Sequence[User], int]:
        stmt = select(User)
        count_stmt = select(func.count()).select_from(User)
        if search:
            pattern = f"%{search}%"
            stmt = stmt.where(
                or_(
                    User.email.ilike(pattern),
                    User.username.ilike(pattern),
                    User.name.ilike(pattern),
                    User.last_name.ilike(pattern),
                )
            )
            count_stmt = count_stmt.where(
                or_(
                    User.email.ilike(pattern),
                    User.username.ilike(pattern),
                    User.name.ilike(pattern),
                    User.last_name.ilike(pattern),
                )
            )
        stmt = stmt.order_by(User.id).offset(page.offset).limit(page.limit)
        users = (await self._session.execute(stmt)).scalars().all()
        total = (await self._session.execute(count_stmt)).scalar_one()
        return list(users), int(total)

    async def create(self, user: User) -> User:
        self._session.add(user)
        await self._session.flush()
        return user

    async def update(self, user: User) -> User:
        await self._session.flush()
        return user

    async def soft_delete(self, user_id: int) -> None:
        user = await self.find_by_id(user_id)
        if user is None:
            return
        user.soft_delete()
        await self._session.flush()

    async def increment_failed_attempts(self, user_id: int) -> int:
        user = await self.find_by_id(user_id)
        if user is None:
            return 0
        user.failed_login_attempts = (user.failed_login_attempts or 0) + 1
        await self._session.flush()
        return user.failed_login_attempts

    async def reset_failed_attempts(self, user_id: int) -> None:
        user = await self.find_by_id(user_id)
        if user is None:
            return
        user.failed_login_attempts = 0
        user.blocked_at = None
        await self._session.flush()

    async def block(self, user_id: int) -> None:
        user = await self.find_by_id(user_id)
        if user is None:
            return
        user.blocked_at = datetime.now(tz=UTC)
        await self._session.flush()

    async def find_by_cedula(self, cedula: str) -> User | None:
        result = await self._session.execute(select(User).where(User.cedula == cedula))
        return result.scalar_one_or_none()
