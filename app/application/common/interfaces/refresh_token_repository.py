"""Repository interface for RefreshToken."""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime


class RefreshTokenRepository(ABC):
    @abstractmethod
    async def add(
        self,
        *,
        token: str,
        user_id: int,
        expires_at: datetime,
        user_agent: str | None = None,
        ip_address: str | None = None,
    ) -> None: ...

    @abstractmethod
    async def find_active(self, token: str) -> dict | None: ...

    @abstractmethod
    async def revoke(self, token: str) -> None: ...

    @abstractmethod
    async def revoke_all_for_user(self, user_id: int) -> int: ...
