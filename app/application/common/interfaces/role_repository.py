"""IRoleRepository interface."""

from __future__ import annotations
from typing import Any

from abc import ABC, abstractmethod
from collections.abc import Sequence


class IRoleRepository(ABC):
    @abstractmethod
    async def find_all(self) -> Sequence[Any]: ...

    @abstractmethod
    async def find_by_id(self, role_id: int) -> Any: ...

    @abstractmethod
    async def find_by_name(self, name: str) -> Any: ...
