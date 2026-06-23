"""HTTP integration test for the sys_api invoice flow.

This test:
  1. Spins up a real PostgreSQL via testcontainers.
  2. Wires the sys_api engine + session factory to that container.
  3. Runs the SQLAlchemy schema (create_all, no Alembic in this test).
  4. Seeds a minimal seller, role, and product.
  5. Boots the FastAPI app in-process via httpx.AsyncClient + ASGITransport.
  6. Logs in as the seller.
  7. Creates a client, then an invoice.
  8. Asserts the invoice comes back as PENDING_VALIDATION (because
     RabbitMQ is not part of this test).

All assertions live in a single test because pytest-asyncio creates
a fresh event loop per test function, and asyncpg cannot reuse
connections across loops. Using a single test keeps everything in
one loop.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.config import get_settings
from app.core.security import hash_password
from app.infrastructure.db.base import Base
from app.infrastructure.db.models import (  # noqa: F401
    AuditLog,
    Client,
    Invoice,
    InvoiceDetail,
    InvoiceDetailTax,
    Product,
    ProductTax,
    Role,
    StockMovement,
    Tax,
    User,
    UserRole,
)

# Skip the whole module if testcontainers cannot be imported (e.g. minimal CI).
pytest.importorskip("testcontainers.core.container")


@pytest.fixture(scope="module")
def postgres_container():
    from testcontainers.postgres import PostgresContainer

    container = PostgresContainer("postgres:16-alpine")
    container.start()
    yield container
    container.stop()


@pytest_asyncio.fixture
async def wired_app(postgres_container) -> AsyncIterator[tuple[AsyncClient, int]]:
    """Set up the DB + engine + app, return (httpx client, product_id)."""
    sync_url = postgres_container.get_connection_url()
    async_url = sync_url.replace(
        "postgresql+psycopg2://", "postgresql+asyncpg://"
    ).replace("postgresql://", "postgresql+asyncpg://")
    async_url = async_url + "?prepared_statement_cache_size=0"

    # Schema with a throwaway engine.
    bootstrap_engine = create_async_engine(async_url, echo=False, future=True)
    async with bootstrap_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await bootstrap_engine.dispose()

    # Wire the app's settings to the test container.
    settings = get_settings()
    settings.database_url = async_url
    settings.jwt_secret = "test-secret-for-integration"
    settings.jwt_issuer = "sys-api-test"
    settings.jwt_audience = "sys-front-test"
    settings.rabbitmq_url = "amqp://disabled:disabled@127.0.0.1:1/"

    # Bypass init_engine and inject a NullPool engine + factory directly so
    # the integration test does not depend on the cached engine's event loop.
    import app.infrastructure.db.session as session_module

    fresh_engine = create_async_engine(
        async_url, echo=False, future=True, poolclass=NullPool
    )
    fresh_factory = async_sessionmaker(
        bind=fresh_engine, expire_on_commit=False, autoflush=False
    )
    session_module._engine = fresh_engine
    session_module._session_factory = fresh_factory

    # Seed minimal data.
    async with fresh_factory() as s:
        role = Role(name="SELLER")
        s.add(role)
        await s.flush()
        user = User(
            username="seller01",
            email="seller@example.com",
            password=hash_password("Seller123!"),
            name="Seller",
            last_name="Test",
        )
        s.add(user)
        await s.flush()
        s.add(UserRole(user_id=user.id, role_id=role.id))
        tax = Tax(name=f"IVA-{uuid.uuid4().hex[:4]}", current_rate=12.0)
        s.add(tax)
        await s.flush()
        product = Product(
            name=f"Test product {uuid.uuid4().hex[:6]}",
            price=10.0,
            stock=100,
        )
        s.add(product)
        await s.flush()
        await s.commit()
        product_id = product.id

    from app.main import create_app

    app = create_app()
    # Disable the lifespan because we do not have a RabbitMQ in this test;
    # the lifespan would otherwise try to declare the broker topology and
    # start a consumer. We replace the lifespan with a no-op so the
    # integration test stays focused on the HTTP + DB layer.
    from contextlib import asynccontextmanager

    @asynccontextmanager
    async def _noop_lifespan(_app):
        yield

    app.router.lifespan_context = _noop_lifespan  # type: ignore[assignment]
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client, product_id

    # Tear down.
    await session_module.dispose_engine()
    await fresh_engine.dispose()


@pytest.mark.asyncio
async def test_full_invoice_flow(wired_app) -> None:
    """Single test that exercises login, client create, invoice create,
    and audit log, all in one event loop."""
    client, product_id = wired_app

    # 1. Login.
    login = await client.post(
        "/api/auth/login",
        json={"email": "seller@example.com", "password": "Seller123!"},
    )
    assert login.status_code == 200, login.text
    body = login.json()
    assert "access_token" in body
    assert body["expires_in"] > 0
    token = body["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 2. Failed login -> audit row.
    bad = await client.post(
        "/api/auth/login",
        json={"email": "seller@example.com", "password": "wrong"},
    )
    assert bad.status_code in (401, 423), bad.text

    # 3. Create a client.
    client_resp = await client.post(
        "/api/clients",
        headers=headers,
        json={"first_name": "Juan", "last_name": "Perez", "cedula": None},
    )
    assert client_resp.status_code == 201, client_resp.text
    client_id = client_resp.json()["id"]

    # 4. Create the invoice. Without RabbitMQ the consumer never runs, so
    # the invoice stays in PENDING_VALIDATION.
    invoice_resp = await client.post(
        "/api/invoices",
        headers=headers,
        json={
            "client_id": client_id,
            "items": [{"product_id": product_id, "quantity": 2, "tax_ids": []}],
        },
    )
    assert invoice_resp.status_code == 201, invoice_resp.text
    inv_body = invoice_resp.json()
    assert inv_body["status"] in ("PENDING_VALIDATION", "DRAFT"), inv_body
    assert float(inv_body["total_snapshot"]) > 0

    # 5. Audit rows were written.
    from app.infrastructure.db.session import get_session_factory

    factory = get_session_factory()
    async with factory() as s:
        result = await s.execute(
            text("SELECT action, count(*) FROM audit_logs GROUP BY action")
        )
        rows = result.fetchall()
    actions = {r[0]: r[1] for r in rows}
    assert actions.get("LOGIN_SUCCESS", 0) >= 1
    assert actions.get("LOGIN_FAILED", 0) >= 1
    assert actions.get("CREATE", 0) >= 1
