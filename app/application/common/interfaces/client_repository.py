"""IClientRepository interface."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Sequence

from app.core.pagination import Page


class IClientRepository(ABC):
    @abstractmethod
    async def find_by_id(self, client_id: int) -> object | None: ...

    @abstractmethod
    async def find_all(
        self, page: Page, search: str | None = None
    ) -> tuple[Sequence[object], int]: ...

    @abstractmethod
    async def create(self, client: object) -> object: ...

    @abstractmethod
    async def update(self, client: object) -> object: ...

    @abstractmethod
    async def soft_delete(self, client_id: int) -> None: ...
