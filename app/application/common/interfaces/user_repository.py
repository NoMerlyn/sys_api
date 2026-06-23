"""IUserRepository interface."""

from __future__ import annotations
from typing import Any

from abc import ABC, abstractmethod
from collections.abc import Sequence

from app.core.pagination import Page


class IUserRepository(ABC):
    @abstractmethod
    async def find_by_id(self, user_id: int) -> Any: ...

    @abstractmethod
    async def find_by_email(self, email: str) -> Any: ...

    @abstractmethod
    async def find_by_username(self, username: str) -> Any: ...

    @abstractmethod
    async def find_all(
        self, page: Page, search: str | None = None
    ) -> tuple[Sequence[Any], int]: ...

    @abstractmethod
    async def create(self, user: Any) -> Any: ...

    @abstractmethod
    async def update(self, user: Any) -> Any: ...

    @abstractmethod
    async def soft_delete(self, user_id: int) -> None: ...

    @abstractmethod
    async def increment_failed_attempts(self, user_id: int) -> int: ...

    @abstractmethod
    async def reset_failed_attempts(self, user_id: int) -> None: ...

    @abstractmethod
    async def block(self, user_id: int) -> None: ...
