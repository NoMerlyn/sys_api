"""aio-pika connection + channel pool and topology declaration.

Single connection per process. A `RobustChannel` is opened from the pool on
demand. Topology (exchange + DLX + DLQ + queues) is declared once at boot.
"""

from __future__ import annotations

import logging

import aio_pika
from aio_pika import ExchangeType, RobustChannel
from aio_pika.abc import AbstractRobustConnection

from app.infrastructure.messaging.topology import (
    DLQ_QUEUE,
    INVOICES_EXCHANGE,
    INVOICES_QUEUE,
    bind_dlq,
)

logger = logging.getLogger(__name__)

_connection: AbstractRobustConnection | None = None


async def get_channel_pool(url: str) -> RobustChannel:
    """Open and cache a robust connection. Returns a fresh channel each call.

    Callers may keep the channel open for the life of their task.
    """
    global _connection
    if _connection is None or _connection.is_closed:
        _connection = await aio_pika.connect_robust(url)
        logger.info("RabbitMQ connection established")
    return await _connection.channel(publisher_confirms=True)  # type: ignore[return-value]


async def declare_topology() -> None:
    """Declare exchange, queues, and bindings. Idempotent."""
    if _connection is None or _connection.is_closed:
        raise RuntimeError("Connection not initialised; call get_channel_pool first.")
    channel = await _connection.channel()
    try:
        exchange = await channel.declare_exchange(
            INVOICES_EXCHANGE, ExchangeType.TOPIC, durable=True
        )
        dlx = await channel.declare_exchange(
            f"{INVOICES_EXCHANGE}.dlx", ExchangeType.TOPIC, durable=True
        )
        main_q = await channel.declare_queue(INVOICES_QUEUE, durable=True)
        await main_q.bind(exchange, routing_key="invoice.#")
        await bind_dlq(channel, dlx)
    finally:
        await channel.close()


async def shutdown_channel_pool() -> None:
    global _connection
    if _connection is not None and not _connection.is_closed:
        await _connection.close()
        logger.info("RabbitMQ connection closed")
    _connection = None


def is_connected() -> bool:
    return _connection is not None and not _connection.is_closed


__all__ = [
    "DLQ_QUEUE",
    "INVOICES_EXCHANGE",
    "INVOICES_QUEUE",
    "declare_topology",
    "get_channel_pool",
    "is_connected",
    "shutdown_channel_pool",
]
