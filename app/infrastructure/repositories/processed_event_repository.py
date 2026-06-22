"""SqlProcessedEventRepository (broker idempotency)."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.common.interfaces.processed_event_repository import (
    IProcessedEventRepository,
)
from app.infrastructure.db.models.processed_event import ProcessedEvent


class SqlProcessedEventRepository(IProcessedEventRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def has_processed(self, event_id: uuid.UUID) -> bool:
        result = await self._session.execute(
            select(ProcessedEvent.event_id).where(ProcessedEvent.event_id == event_id)
        )
        return result.scalar_one_or_none() is not None

    async def mark_processed(self, event_id: uuid.UUID, event_type: str, payload_hash: str) -> None:
        # ON CONFLICT DO NOTHING — idempotent even under concurrent inserts.
        stmt = (
            pg_insert(ProcessedEvent)
            .values(event_id=event_id, event_type=event_type, payload_hash=payload_hash)
            .on_conflict_do_nothing(index_elements=["event_id"])
        )
        await self._session.execute(stmt)
        await self._session.flush()
