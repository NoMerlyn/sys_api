"""IErrorLogRepository interface."""

from __future__ import annotations
from typing import Any

from abc import ABC, abstractmethod
from collections.abc import Sequence

from app.core.pagination import Page


class IErrorLogRepository(ABC):
    @abstractmethod
    async def find_all(
        self, page: Page, search: str | None = None
    ) -> tuple[Sequence[Any], int]: ...

    @abstractmethod
    async def create(self, log: Any) -> Any: ...
