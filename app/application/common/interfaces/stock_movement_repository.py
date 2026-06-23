"""IStockMovementRepository interface."""

from __future__ import annotations
from typing import Any

from abc import ABC, abstractmethod


class IStockMovementRepository(ABC):
    @abstractmethod
    async def create(self, movement: Any) -> Any: ...
