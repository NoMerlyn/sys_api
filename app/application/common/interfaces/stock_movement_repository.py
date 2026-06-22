"""IStockMovementRepository interface."""

from __future__ import annotations

from abc import ABC, abstractmethod


class IStockMovementRepository(ABC):
    @abstractmethod
    async def create(self, movement: object) -> object: ...
