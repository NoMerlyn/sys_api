"""Repository interface for AuditLog."""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime


class AuditLogRepository(ABC):
    @abstractmethod
    async def add(
        self,
        *,
        action: str,
        entity: str,
        entity_id: int | None = None,
        user_id: int | None = None,
        detail: str | None = None,
        ip_address: str | None = None,
    ) -> None:
        raise NotImplementedError

    @abstractmethod
    async def list(
        self,
        *,
        page: int,
        limit: int,
        action: str | None = None,
        entity: str | None = None,
        user_id: int | None = None,
        since: datetime | None = None,
    ) -> tuple[list[dict], int]:
        raise NotImplementedError