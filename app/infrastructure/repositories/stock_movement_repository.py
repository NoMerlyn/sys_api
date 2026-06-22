"""SqlStockMovementRepository."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.application.common.interfaces.stock_movement_repository import (
    IStockMovementRepository,
)
from app.infrastructure.db.models.stock_movement import StockMovement


class SqlStockMovementRepository(IStockMovementRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, movement: StockMovement) -> StockMovement:
        self._session.add(movement)
        await self._session.flush()
        return movement
