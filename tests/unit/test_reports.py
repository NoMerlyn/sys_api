"""Sales report handler tests.

Seeds a minimal dataset (1 seller, 1 client, 2 products, 3 invoices
in CONFIRMED state + 1 in DRAFT) and asserts each handler returns
the expected aggregates.
"""

from __future__ import annotations

import contextlib
import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from decimal import Decimal

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.application.reports import (
    SalesByDayHandler,
    SalesByDayQuery,
    SalesSummaryHandler,
    SalesSummaryQuery,
    TopClientsHandler,
    TopClientsQuery,
    TopProductsHandler,
    TopProductsQuery,
    TopSellersHandler,
    TopSellersQuery,
)
from app.config import get_settings
from app.core.security import hash_password
from app.infrastructure.db import session as session_module
from app.infrastructure.db.base import Base
from app.infrastructure.db.models import (  # noqa: F401
    Invoice,
    InvoiceDetail,
    Product,
    Role,
    Tax,
    User,
    UserRole,
)
from app.infrastructure.db.models.invoice import InvoiceStatus


@pytest_asyncio.fixture
async def wired_db() -> AsyncIterator[None]:
    async_url = f"sqlite+aiosqlite:///{uuid.uuid4().hex}.db"

    bootstrap = create_async_engine(async_url, echo=False, future=True)
    async with bootstrap.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await bootstrap.dispose()

    settings = get_settings()
    settings.database_url = async_url
    settings.jwt_secret = "test"
    settings.jwt_issuer = "t"
    settings.jwt_audience = "t"
    settings.rabbitmq_url = "amqp://disabled:127.0.0.1:1/"

    await session_module.dispose_engine()
    engine = create_async_engine(async_url, echo=False, future=True)
    factory = async_sessionmaker(bind=engine, expire_on_commit=False, autoflush=False)
    session_module._engine = engine
    session_module._session_factory = factory

    factory2 = factory
    async with factory2() as s:
        role = Role(name="SELLER")
        s.add(role)
        await s.flush()
        user = User(
            username="u1",
            email="u1@example.com",
            password=hash_password("ValidPass1!"),
            name="S",
            last_name="O",
        )
        s.add(user)
        await s.flush()
        s.add(UserRole(user_id=user.id, role_id=role.id))

        p1 = Product(name="Pen", price=Decimal("10.00"), stock=100)
        p2 = Product(name="Book", price=Decimal("25.00"), stock=50)
        s.add_all([p1, p2])
        await s.flush()

        # 3 confirmed invoices
        for i in range(3):
            inv = Invoice(
                user_id=user.id,
                client_id=None,
                client_name_snapshot="Consumidor final",
                seller_name_snapshot="S O",
                status=InvoiceStatus.CONFIRMED,
                issue_date=datetime(2026, 1, i + 1, tzinfo=UTC),
                subtotal_snapshot=Decimal("100.00"),
                tax_total_snapshot=Decimal("12.00"),
                total_snapshot=Decimal("112.00"),
            )
            s.add(inv)
            await s.flush()
            d = InvoiceDetail(
                invoice_id=inv.id,
                product_id=p1.id if i % 2 == 0 else p2.id,
                product_name=p1.name if i % 2 == 0 else p2.name,
                quantity=2,
                unit_price_snapshot=Decimal("50.00") if i % 2 == 0 else Decimal("50.00"),
            )
            s.add(d)

        # 1 draft invoice (should NOT appear in CONFIRMED-only queries)
        draft = Invoice(
            user_id=user.id,
            client_id=None,
            client_name_snapshot="Consumidor final",
            seller_name_snapshot="S O",
            status=InvoiceStatus.DRAFT,
            issue_date=datetime(2026, 1, 5, tzinfo=UTC),
            subtotal_snapshot=Decimal("0"),
            tax_total_snapshot=Decimal("0"),
            total_snapshot=Decimal("0"),
        )
        s.add(draft)
        await s.commit()

    yield

    await session_module.dispose_engine()
    await engine.dispose()
    with contextlib.suppress(FileNotFoundError):
        import os
        os.remove(async_url.split("/")[-1])


@pytest.mark.asyncio
async def test_summary_excludes_drafts(wired_db) -> None:
    handler = SalesSummaryHandler()
    async with session_module.get_session_factory()() as session:
        result = await handler.handle(SalesSummaryQuery(), session)
    assert result["total_invoices"] == 3  # the draft is not counted
    assert float(result["total_amount"]) == 336.0  # 3 * 112
    assert float(result["avg_amount"]) == 112.0
    assert result["by_status"]["CONFIRMED"] == 3
    assert result["by_status"]["DRAFT"] == 1


@pytest.mark.asyncio
async def test_top_products_orders_by_revenue(wired_db) -> None:
    handler = TopProductsHandler()
    async with session_module.get_session_factory()() as session:
        rows = await handler.handle(TopProductsQuery(limit=10), session)
    assert len(rows) == 2
    # Pen appears in invoices 0 and 2 (qty 2 each); Book in invoice 1
    # (qty 2). Revenue = unit_price * qty = 50 * 2 = 100 per line, so
    # Pen total is 200 and Book total is 100.
    by_name = {r["product_name"]: float(r["revenue"]) for r in rows}
    assert by_name == {"Pen": 200.0, "Book": 100.0}
    assert rows[0]["product_name"] == "Pen"  # ordered by revenue desc


@pytest.mark.asyncio
async def test_top_clients_aggregates_by_invoice(wired_db) -> None:
    handler = TopClientsHandler()
    async with session_module.get_session_factory()() as session:
        rows = await handler.handle(TopClientsQuery(limit=10), session)
    assert len(rows) == 1
    assert rows[0]["invoices"] == 3
    assert float(rows[0]["spent"]) == 336.0
    assert rows[0]["client_name"] == "Consumidor final"


@pytest.mark.asyncio
async def test_top_sellers(wired_db) -> None:
    handler = TopSellersHandler()
    async with session_module.get_session_factory()() as session:
        rows = await handler.handle(TopSellersQuery(limit=10), session)
    assert len(rows) == 1
    assert rows[0]["invoices"] == 3
    assert float(rows[0]["sold"]) == 336.0


@pytest.mark.asyncio
async def test_by_day_returns_daily_rows(wired_db) -> None:
    handler = SalesByDayHandler()
    async with session_module.get_session_factory()() as session:
        rows = await handler.handle(SalesByDayQuery(), session)
    # 3 distinct days for the 3 confirmed invoices
    assert len(rows) == 3
    for r in rows:
        assert r["invoices"] == 1
        assert float(r["revenue"]) == 112.0
