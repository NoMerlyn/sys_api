"""SqlProductRepository."""

from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.common.interfaces.product_repository import IProductRepository
from app.core.pagination import Page
from app.infrastructure.db.models.product import Product


class SqlProductRepository(IProductRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def find_by_id(self, product_id: int) -> Product | None:
        result = await self._session.execute(select(Product).where(Product.id == product_id))
        return result.scalar_one_or_none()

    async def find_all(
        self, page: Page, search: str | None = None
    ) -> tuple[Sequence[Product], int]:
        stmt = select(Product)
        count_stmt = select(func.count()).select_from(Product)
        if search:
            pattern = f"%{search}%"
            filt = or_(
                Product.name.ilike(pattern),
            )
            stmt = stmt.where(filt)
            count_stmt = count_stmt.where(filt)
        stmt = stmt.order_by(Product.id).offset(page.offset).limit(page.limit)
        rows = (await self._session.execute(stmt)).scalars().all()
        total = (await self._session.execute(count_stmt)).scalar_one()
        return list(rows), int(total)

    async def find_for_sale(
        self, page: Page, search: str | None = None
    ) -> tuple[Sequence[Product], int]:
        available = and_(Product.is_active.is_(True), Product.stock > 0)
        stmt = select(Product).where(available)
        count_stmt = select(func.count()).select_from(Product).where(available)
        if search:
            pattern = f"%{search}%"
            filt = or_(Product.name.ilike(pattern))
            stmt = stmt.where(filt)
            count_stmt = count_stmt.where(filt)
        stmt = stmt.order_by(Product.name).offset(page.offset).limit(page.limit)
        rows = (await self._session.execute(stmt)).scalars().all()
        total = (await self._session.execute(count_stmt)).scalar_one()
        return list(rows), int(total)

    async def create(self, product: Product) -> Product:
        self._session.add(product)
        await self._session.flush()
        return product

    async def update(self, product: Product) -> Product:
        product.version = (product.version or 0) + 1
        await self._session.flush()
        return product

    async def soft_delete(self, product_id: int) -> None:
        product = await self.find_by_id(product_id)
        if product is None:
            return
        product.soft_delete()
        await self._session.flush()

    async def decrement_stock(self, product_id: int, quantity: int) -> tuple[int, int]:
        """Return (previous_stock, new_stock). Caller must enforce quantity limits."""
        product = await self.find_by_id(product_id)
        if product is None:
            return (0, 0)
        previous = int(product.stock or 0)
        product.stock = previous - quantity
        product.version = (product.version or 0) + 1
        await self._session.flush()
        return previous, int(product.stock or 0)
