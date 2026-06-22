"""IRoleRepository interface."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Sequence


class IRoleRepository(ABC):
    @abstractmethod
    async def find_all(self) -> Sequence[object]: ...

    @abstractmethod
    async def find_by_id(self, role_id: int) -> object | None: ...

    @abstractmethod
    async def find_by_name(self, name: str) -> object | None: ...
