"""ITaxRepository interface."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Sequence


class ITaxRepository(ABC):
    @abstractmethod
    async def find_all(self) -> Sequence[object]: ...

    @abstractmethod
    async def find_by_id(self, tax_id: int) -> object | None: ...

    @abstractmethod
    async def create(self, tax: object) -> object: ...

    @abstractmethod
    async def update(self, tax: object) -> object: ...

    @abstractmethod
    async def soft_delete(self, tax_id: int) -> None: ...
