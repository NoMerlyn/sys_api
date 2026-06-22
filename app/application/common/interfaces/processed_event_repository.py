"""IProcessedEventRepository interface (broker idempotency)."""

from __future__ import annotations

import uuid
from abc import ABC, abstractmethod


class IProcessedEventRepository(ABC):
    @abstractmethod
    async def has_processed(self, event_id: uuid.UUID) -> bool: ...

    @abstractmethod
    async def mark_processed(
        self, event_id: uuid.UUID, event_type: str, payload_hash: str
    ) -> None: ...
