"""Broker publishers.

`InvoiceCreatedPublisher` is implemented in L4 (it needs the full event
payload contract). This stub keeps the package importable.
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import UTC, datetime
from typing import Any

from aio_pika import DeliveryMode, Message
from aio_pika.abc import AbstractChannel

from app.infrastructure.messaging.topology import INVOICES_EXCHANGE

logger = logging.getLogger(__name__)


def _envelope(event_type: str, data: dict[str, Any]) -> dict[str, Any]:
    return {
        "event_id": str(uuid.uuid4()),
        "event_type": event_type,
        "occurred_at": datetime.now(tz=UTC).isoformat(),
        "producer": "sys_api",
        "schema_version": "1",
        "data": data,
    }


async def publish_event(channel: AbstractChannel, routing_key: str, data: dict[str, Any]) -> None:
    """Publish a single event with the standard envelope."""
    event_type = routing_key
    payload = _envelope(event_type, data)
    body = json.dumps(payload, default=str).encode("utf-8")
    exchange = await channel.get_exchange(INVOICES_EXCHANGE, ensure=False)
    await exchange.publish(
        Message(
            body=body,
            content_type="application/json",
            delivery_mode=DeliveryMode.PERSISTENT,
            headers={"event_id": payload["event_id"], "event_type": event_type},
        ),
        routing_key=routing_key,
    )
    logger.info("Published %s (event_id=%s)", event_type, payload["event_id"])


__all__ = ["publish_event"]
