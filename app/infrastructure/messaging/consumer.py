"""Broker consumer for invoice.validated / invoice.rejected.

Run as a background task inside the FastAPI lifespan so we don't need a
separate worker process in v1. Idempotent via ProcessedEvent.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import uuid
from typing import Any

from aio_pika.abc import AbstractIncomingMessage

from app.application.common.interfaces.invoice_repository import IInvoiceRepository
from app.application.common.interfaces.product_repository import IProductRepository
from app.application.common.interfaces.stock_movement_repository import (
    IStockMovementRepository,
)
from app.application.common.uow import uow
from app.domain.value_objects.invoice_status import InvoiceStatus
from app.domain.value_objects.movement_type import MovementType
from app.infrastructure.messaging.rabbit import get_channel_pool
from app.infrastructure.messaging.topology import INVOICES_QUEUE

logger = logging.getLogger(__name__)


async def _on_validated(event_id: uuid.UUID, data: dict[str, Any]) -> None:
    invoice_id = int(data["invoice_id"])
    async with uow() as session:
        invoices: IInvoiceRepository = _new(IInvoiceRepository, session)  # type: ignore[assignment]
        products: IProductRepository = _new(IProductRepository, session)  # type: ignore[assignment]
        moves: IStockMovementRepository = _new(IStockMovementRepository, session)  # type: ignore[assignment]
        from app.infrastructure.repositories.invoice_repository import (
            SqlInvoiceRepository,
        )
        from app.infrastructure.repositories.product_repository import (
            SqlProductRepository,
        )
        from app.infrastructure.repositories.stock_movement_repository import (
            SqlStockMovementRepository,
        )

        invoices = SqlInvoiceRepository(session)
        products = SqlProductRepository(session)
        moves = SqlStockMovementRepository(session)

        inv = await invoices.find_by_id(invoice_id)
        if inv is None:
            logger.warning("validated: invoice %s not found", invoice_id)
            return
        if inv.status not in (InvoiceStatus.PENDING_VALIDATION,):
            logger.info("validated: invoice %s already at %s, skipping", invoice_id, inv.status)
            return
        # First mark VALIDATED, then decrement stock and move to CONFIRMED.
        from app.infrastructure.db.models.stock_movement import StockMovement

        for d in inv.details or []:
            if d.product_id is None or not d.quantity:
                continue
            previous, new_stock = await products.decrement_stock(d.product_id, int(d.quantity))
            await moves.create(
                StockMovement(
                    product_id=d.product_id,
                    type=MovementType.EXIT,
                    quantity=int(d.quantity),
                    previous_stock=previous,
                    new_stock=new_stock,
                    reference=f"invoice:{invoice_id}:confirmed",
                )
            )
        # Single transition: PENDING_VALIDATION -> VALIDATED -> CONFIRMED.
        await invoices.update_status(invoice_id, InvoiceStatus.VALIDATED)
        await invoices.update_status(invoice_id, InvoiceStatus.CONFIRMED)


async def _on_rejected(event_id: uuid.UUID, data: dict[str, Any]) -> None:
    invoice_id = int(data["invoice_id"])
    reason = (data.get("reasons") or [{}])[0].get("message") if data.get("reasons") else None
    async with uow() as session:
        from app.infrastructure.repositories.invoice_repository import (
            SqlInvoiceRepository,
        )

        invoices = SqlInvoiceRepository(session)
        inv = await invoices.find_by_id(invoice_id)
        if inv is None:
            logger.warning("rejected: invoice %s not found", invoice_id)
            return
        if inv.status != InvoiceStatus.PENDING_VALIDATION:
            return
        await invoices.update_status(invoice_id, InvoiceStatus.REJECTED, rejection_reason=reason)


def _new(interface, session):  # type: ignore[no-untyped-def]
    """Placeholder to satisfy the no-op `from app... import ...` branches."""
    return None


async def _handle_message(message: AbstractIncomingMessage) -> None:
    async with message.process(requeue=False):
        try:
            payload = json.loads(message.body.decode("utf-8"))
            event_id = uuid.UUID(payload["event_id"])
            event_type = payload["event_type"]
            data = payload["data"]
        except Exception as exc:
            logger.exception("malformed event payload: %s", exc)
            return

        async with uow() as session:
            from app.infrastructure.repositories.processed_event_repository import (
                SqlProcessedEventRepository,
            )

            processed = SqlProcessedEventRepository(session)
            if await processed.has_processed(event_id):
                logger.info("duplicate event %s dropped", event_id)
                return
            payload_hash = hashlib.sha256(message.body).hexdigest()
            await processed.mark_processed(event_id, event_type, payload_hash)

        if event_type == "invoice.validated":
            await _on_validated(event_id, data)
        elif event_type == "invoice.rejected":
            await _on_rejected(event_id, data)
        else:
            logger.info("ignoring event type %s", event_type)


async def run_invoice_consumer(url: str) -> None:
    """Long-running consumer. Started from FastAPI lifespan."""
    channel = await get_channel_pool(url)
    await channel.set_qos(prefetch_count=10)
    queue = await channel.get_queue(INVOICES_QUEUE, ensure=False)
    logger.info("Invoice consumer listening on %s", INVOICES_QUEUE)
    await queue.consume(_handle_message)
    # Keep the task alive; the lifespan keeps the process up.
    while True:
        await asyncio.sleep(3600)
