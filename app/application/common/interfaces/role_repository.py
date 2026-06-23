"""IRoleRepository interface."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Sequence
from typing import Any


class IRoleRepository(ABC):
    @abstractmethod
    async def find_all(self) -> Sequence[Any]: ...

    @abstractmethod
    async def find_by_id(self, role_id: int) -> Any: ...

    @abstractmethod
    async def find_by_name(self, name: str) -> Any: ...
