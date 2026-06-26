"""SqlClientRepository."""

from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.common.interfaces.client_repository import IClientRepository
from app.core.pagination import Page
from app.infrastructure.db.models.client import Client


class SqlClientRepository(IClientRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def find_by_id(self, client_id: int) -> Client | None:
        result = await self._session.execute(select(Client).where(Client.id == client_id))
        return result.scalar_one_or_none()

    async def find_all(self, page: Page, search: str | None = None, is_active: bool | None = None) -> tuple[Sequence[Client], int]:
        stmt = select(Client)
        count_stmt = select(func.count()).select_from(Client)
        if is_active is not None:
            stmt = stmt.where(Client.is_active == is_active)
            count_stmt = count_stmt.where(Client.is_active == is_active)
        if search:
            pattern = f"%{search}%"
            full_name = func.concat(
                func.coalesce(Client.first_name, ""),
                " ",
                func.coalesce(Client.last_name, "")
            )
            filt = or_(
                Client.first_name.ilike(pattern),
                Client.last_name.ilike(pattern),
                full_name.ilike(pattern),
                Client.email.ilike(pattern),
                Client.cedula.ilike(pattern),
            )
            stmt = stmt.where(filt)
            count_stmt = count_stmt.where(filt)
        stmt = stmt.order_by(Client.id).offset(page.offset).limit(page.limit)
        rows = (await self._session.execute(stmt)).scalars().all()
        total = (await self._session.execute(count_stmt)).scalar_one()
        return list(rows), int(total)

    async def create(self, client: Client) -> Client:
        self._session.add(client)
        await self._session.flush()
        return client

    async def update(self, client: Client) -> Client:
        await self._session.flush()
        return client

    async def soft_delete(self, client_id: int) -> None:
        client = await self.find_by_id(client_id)
        if client is None:
            return
        client.soft_delete()
        await self._session.flush()

    async def find_by_cedula(self, cedula: str) -> Client | None:
        result = await self._session.execute(select(Client).where(Client.cedula == cedula))
        return result.scalar_one_or_none()
