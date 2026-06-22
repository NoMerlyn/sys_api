"""IProductRepository interface."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Sequence

from app.core.pagination import Page


class IProductRepository(ABC):
    @abstractmethod
    async def find_by_id(self, product_id: int) -> object | None: ...

    @abstractmethod
    async def find_all(
        self, page: Page, search: str | None = None
    ) -> tuple[Sequence[object], int]: ...

    @abstractmethod
    async def find_for_sale(
        self, page: Page, search: str | None = None
    ) -> tuple[Sequence[object], int]: ...

    @abstractmethod
    async def create(self, product: object) -> object: ...

    @abstractmethod
    async def update(self, product: object) -> object: ...

    @abstractmethod
    async def soft_delete(self, product_id: int) -> None: ...

    @abstractmethod
    async def decrement_stock(self, product_id: int, quantity: int) -> tuple[int, int]: ...
