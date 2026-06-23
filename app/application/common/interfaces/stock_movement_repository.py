"""IStockMovementRepository interface."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class IStockMovementRepository(ABC):
    @abstractmethod
    async def create(self, movement: Any) -> Any: ...
