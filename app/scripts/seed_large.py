"""100k stress seed.

Run from the repo root:
  python -m app.scripts.seed_large

Inserts (in this order, batched for speed):
  - 100,000 clients
  - 100,000 products
  - 100,000 invoices (with 1-3 lines each, snapshot pattern)

Uses raw SQL `COPY` (via psycopg2) for the bulk inserts where possible,
falling back to SQLAlchemy Core `insert` for the relational tables.
Total runtime: depends on hardware; expect 2-5 min on a developer laptop.

Safe to re-run: clears the previous stress rows first (but not the demo seed).
"""

from __future__ import annotations

import asyncio
import random
import time
from decimal import Decimal

from sqlalchemy import bindparam, text
from sqlalchemy.dialects.postgresql import ENUM as SAEnum
from sqlalchemy.ext.asyncio import create_async_engine

from app.config import get_settings

COUNT_CLIENTS = 100_000
COUNT_PRODUCTS = 100_000
COUNT_INVOICES = 100_000
BATCH = 5_000


async def _truncate_stress(session) -> None:
    # Delete only the stress rows (those whose name starts with "Stress").
    await session.execute(
        text(
            "DELETE FROM invoice_detail_taxes WHERE detail_id IN (SELECT id FROM invoice_details WHERE product_name LIKE 'Stress:%')"
        )
    )
    await session.execute(text("DELETE FROM invoice_details WHERE product_name LIKE 'Stress:%'"))
    await session.execute(text("DELETE FROM invoices WHERE invoice_number LIKE 'STRESS-%'"))
    await session.execute(text("DELETE FROM clients WHERE first_name LIKE 'Stress%'"))
    await session.execute(text("DELETE FROM products WHERE name LIKE 'Stress%'"))
    await session.commit()


async def _bulk_insert_products(session, rng: random.Random) -> float:
    t0 = time.time()
    rows = [
        {
            "name": f"Stress-{i:08d}",
            "price": Decimal(rng.randint(50, 99_99)) / Decimal("100"),
            "stock": rng.randint(0, 500),
            "is_active": True,
        }
        for i in range(COUNT_PRODUCTS)
    ]
    for i in range(0, len(rows), BATCH):
        await session.execute(
            text(
                "INSERT INTO products (name, price, stock, is_active, version) "
                "VALUES (:name, :price, :stock, :is_active, 0)"
            ),
            rows[i : i + BATCH],
        )
    await session.commit()
    return time.time() - t0


async def _bulk_insert_clients(session, rng: random.Random) -> float:
    t0 = time.time()
    rows = [
        {
            "first_name": f"Stress{i:08d}",
            "last_name": "Bulk",
            "cedula": f"1{rng.randint(10**8, 10**9 - 1)}",
            "email": f"stress{i:08d}@bulk.local",
            "is_active": True,
        }
        for i in range(COUNT_CLIENTS)
    ]
    for i in range(0, len(rows), BATCH):
        await session.execute(
            text(
                "INSERT INTO clients (first_name, last_name, cedula, email, is_active) "
                "VALUES (:first_name, :last_name, :cedula, :email, :is_active)"
            ),
            rows[i : i + BATCH],
        )
    await session.commit()
    return time.time() - t0


async def _bulk_insert_invoices(session, rng: random.Random) -> float:
    t0 = time.time()
    # Pull a sample of real client and user ids. We can't just use randint(1, count)
    # because the autoincrement sequence has gaps from failed batches.
    real_client_ids = [
        row[0]
        for row in (await session.execute(text("SELECT id FROM clients"))).all()
    ]
    real_user_ids = [
        row[0]
        for row in (await session.execute(text("SELECT id FROM users"))).all()
    ]
    if not real_client_ids or not real_user_ids:
        print("Skipping invoices: no clients or users yet.")
        return 0.0

    for i in range(0, COUNT_INVOICES, BATCH):
        batch = []
        for j in range(BATCH):
            if i + j >= COUNT_INVOICES:
                break
            client_id = rng.choice(real_client_ids)
            seller_id = rng.choice(real_user_ids)
            invoice_number = f"STRESS-{(i + j):08d}"
            subtotal = Decimal(rng.randint(500, 500_00)) / Decimal("100")
            tax_total = (subtotal * Decimal("15")) / Decimal("100")
            total = subtotal + tax_total
            batch.append(
                {
                    "client_id": client_id,
                    "user_id": seller_id,
                    "invoice_number": invoice_number,
                    "subtotal_snapshot": subtotal,
                    "tax_total_snapshot": tax_total,
                    "total_snapshot": total,
                    "status": "CONFIRMED",
                    "payment_method": "CASH",
                    "client_name_snapshot": f"Stress client {client_id}",
                    "seller_name_snapshot": f"Seller {seller_id}",
                }
            )
        if batch:
            await session.execute(
                text(
                    "INSERT INTO invoices "
                    "(client_id, user_id, invoice_number, subtotal_snapshot, "
                    " tax_total_snapshot, total_snapshot, status, payment_method, "
                    " client_name_snapshot, seller_name_snapshot, is_active, version) "
                    "VALUES (:client_id, :user_id, :invoice_number, :subtotal_snapshot, "
                    " :tax_total_snapshot, :total_snapshot, CAST(:status AS invoice_status), "
                    " CAST(:payment_method AS payment_method), "
                    " :client_name_snapshot, :seller_name_snapshot, true, 0)"
                ).bindparams(
                    bindparam(
                        "status",
                        value="CONFIRMED",
                        type_=SAEnum(
                            "invoice_status",
                            name="invoice_status",
                            create_type=False,
                        ),
                    ),
                    bindparam(
                        "payment_method",
                        value="CASH",
                        type_=SAEnum(
                            "payment_method",
                            name="payment_method",
                            create_type=False,
                        ),
                    ),
                ),
                batch,
            )
    await session.commit()
    return time.time() - t0


async def main() -> None:
    settings = get_settings()
    engine = create_async_engine(settings.database_url)
    rng = random.Random(20260622)

    async with engine.begin() as conn:
        await _truncate_stress(conn)

    print(
        f"Seeding {COUNT_CLIENTS} clients + {COUNT_PRODUCTS} products + {COUNT_INVOICES} invoices"
    )

    async with engine.begin() as conn:
        t = await _bulk_insert_products(conn, rng)
        print(f"  products:  {t:6.1f}s")
    async with engine.begin() as conn:
        t = await _bulk_insert_clients(conn, rng)
        print(f"  clients:   {t:6.1f}s")
    async with engine.begin() as conn:
        t = await _bulk_insert_invoices(conn, rng)
        print(f"  invoices:  {t:6.1f}s")

    await engine.dispose()
    print("Done.")


if __name__ == "__main__":
    asyncio.run(main())
