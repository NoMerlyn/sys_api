"""IClientRepository interface."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Sequence
from typing import Any

from app.core.pagination import Page


class IClientRepository(ABC):
    @abstractmethod
    async def find_by_id(self, client_id: int) -> Any: ...

    @abstractmethod
    async def find_all(
        self, page: Page, search: str | None = None
    ) -> tuple[Sequence[Any], int]: ...

    @abstractmethod
    async def create(self, client: Any) -> Any: ...

    @abstractmethod
    async def update(self, client: Any) -> Any: ...

    @abstractmethod
    async def soft_delete(self, client_id: int) -> None: ...
