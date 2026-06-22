"""IBlockedUserRepository interface (preserved for legacy parity)."""

from __future__ import annotations

from abc import ABC, abstractmethod


class IBlockedUserRepository(ABC):
    @abstractmethod
    async def find_by_user_id(self, user_id: int) -> object | None: ...

    @abstractmethod
    async def upsert(
        self, user_id: int, failed_attempts: int, blocked_at: object | None
    ) -> object: ...
