"""ITaxRepository interface."""

from __future__ import annotations
from typing import Any

from abc import ABC, abstractmethod
from collections.abc import Sequence


class ITaxRepository(ABC):
    @abstractmethod
    async def find_all(self) -> Sequence[Any]: ...

    @abstractmethod
    async def find_by_id(self, tax_id: int) -> Any: ...

    @abstractmethod
    async def create(self, tax: Any) -> Any: ...

    @abstractmethod
    async def update(self, tax: Any) -> Any: ...

    @abstractmethod
    async def soft_delete(self, tax_id: int) -> None: ...
