"""SqlTaxRepository."""

from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.common.interfaces.tax_repository import ITaxRepository
from app.infrastructure.db.models.tax import Tax


class SqlTaxRepository(ITaxRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def find_all(self) -> Sequence[Tax]:
        result = await self._session.execute(select(Tax).order_by(Tax.name))
        return list(result.scalars().all())

    async def find_by_id(self, tax_id: int) -> Tax | None:
        result = await self._session.execute(select(Tax).where(Tax.id == tax_id))
        return result.scalar_one_or_none()

    async def create(self, tax: Tax) -> Tax:
        self._session.add(tax)
        await self._session.flush()
        return tax

    async def update(self, tax: Tax) -> Tax:
        await self._session.flush()
        return tax

    async def soft_delete(self, tax_id: int) -> None:
        tax = await self.find_by_id(tax_id)
        if tax is None:
            return
        tax.soft_delete()
        await self._session.flush()
