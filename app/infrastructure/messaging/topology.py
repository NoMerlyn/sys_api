"""Broker topology constants and the DLQ binding helper.

Single source of truth for exchange/queue names. The validator service
re-imports the same constants.
"""

from __future__ import annotations

from aio_pika.abc import AbstractChannel, AbstractExchange

INVOICES_EXCHANGE = "invoices.events"
INVOICES_QUEUE = "invoices.events.main"
DLQ_QUEUE = "invoices.events.dlq"


async def declare_topology() -> None:
    """Placeholder kept for backwards compat. The real implementation is in
    `app.infrastructure.messaging.rabbit.declare_topology` which calls this
    module's binding helper."""
    raise RuntimeError("Use app.infrastructure.messaging.rabbit.declare_topology")


async def bind_dlq(channel: AbstractChannel, dlx: AbstractExchange) -> None:
    """Declare the DLQ and bind it to the DLX with a wildcard key."""
    dlq = await channel.declare_queue(DLQ_QUEUE, durable=True)
    await dlq.bind(dlx, routing_key="#")
