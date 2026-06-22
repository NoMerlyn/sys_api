"""Demo seed: 1 admin, 1 seller, 50 products, 50 clients, 2 taxes.

Idempotent: looks up by unique key (email, name) before inserting.
"""

from __future__ import annotations

import asyncio
import random
from decimal import Decimal

from sqlalchemy import select

from app.config import get_settings
from app.core.security import hash_password
from app.infrastructure.db.models.client import Client
from app.infrastructure.db.models.product import Product
from app.infrastructure.db.models.role import Role
from app.infrastructure.db.models.tax import Tax
from app.infrastructure.db.models.user import User
from app.infrastructure.db.models.user_role import UserRole
from app.infrastructure.db.session import init_engine, session_scope

DEMO_USERS = [
    {
        "username": "admin",
        "name": "Ada",
        "last_name": "Admin",
        "email": "admin@pos.local",
        "password": "Admin123!",
        "cedula": "1712345678",
    },
    {
        "username": "seller",
        "name": "Sol",
        "last_name": "Vendedora",
        "email": "seller@pos.local",
        "password": "Seller123!",
        "cedula": "1798765432",
    },
]

DEMO_TAXES = [
    {"name": "IVA 15%", "current_rate": Decimal("15.00")},
    {"name": "IVA 0%", "current_rate": Decimal("0.00")},
]

DEMO_PRODUCT_COUNT = 50
DEMO_CLIENT_COUNT = 50


async def _ensure_role(session, name: str) -> Role:
    existing = (await session.execute(select(Role).where(Role.name == name))).scalar_one_or_none()
    if existing:
        return existing
    role = Role(name=name, description=name.title())
    session.add(role)
    await session.flush()
    return role


async def _ensure_user(session, role: Role, spec: dict) -> User:
    existing = (
        await session.execute(select(User).where(User.email == spec["email"]))
    ).scalar_one_or_none()
    if existing:
        return existing
    user = User(
        username=spec["username"],
        name=spec["name"],
        last_name=spec["last_name"],
        cedula=spec.get("cedula"),
        email=spec["email"],
        password=hash_password(spec["password"]),
    )
    session.add(user)
    await session.flush()
    session.add(UserRole(user_id=user.id, role_id=role.id))
    return user


async def _ensure_tax(session, spec: dict) -> Tax:
    existing = (
        await session.execute(select(Tax).where(Tax.name == spec["name"]))
    ).scalar_one_or_none()
    if existing:
        return existing
    tax = Tax(name=spec["name"], current_rate=spec["current_rate"])
    session.add(tax)
    await session.flush()
    return tax


async def _ensure_product(session, name: str, price: Decimal, stock: int) -> Product:
    existing = (
        await session.execute(select(Product).where(Product.name == name))
    ).scalar_one_or_none()
    if existing:
        return existing
    product = Product(name=name, price=price, stock=stock, is_active=True)
    session.add(product)
    await session.flush()
    return product


async def _ensure_client(session, first: str, last: str, email: str) -> Client:
    existing = (
        await session.execute(select(Client).where(Client.email == email))
    ).scalar_one_or_none()
    if existing:
        return existing
    client = Client(first_name=first, last_name=last, email=email, is_active=True)
    session.add(client)
    await session.flush()
    return client


async def main() -> None:
    settings = get_settings()
    init_engine(settings.database_url_sync)
    rng = random.Random(42)

    async with session_scope() as session:
        admin_role = await _ensure_role(session, "ADMINISTRATOR")
        seller_role = await _ensure_role(session, "SELLER")
        for spec in DEMO_USERS:
            role = admin_role if "admin" in spec["username"] else seller_role
            await _ensure_user(session, role, spec)

        taxes = []
        for spec in DEMO_TAXES:
            taxes.append(await _ensure_tax(session, spec))

        for i in range(1, DEMO_PRODUCT_COUNT + 1):
            name = f"Producto {i:03d}"
            price = Decimal(rng.randint(50, 9999)) / Decimal("100")
            stock = rng.randint(0, 200)
            await _ensure_product(session, name, price, stock)

        for i in range(1, DEMO_CLIENT_COUNT + 1):
            first = f"Cliente{i:03d}"
            last = "Demo"
            email = f"cliente{i:03d}@pos.local"
            await _ensure_client(session, first, last, email)

    print("Demo seed complete.")
    print("  - 2 users (admin@pos.local, seller@pos.local)")
    print(f"  - {len(DEMO_TAXES)} taxes")
    print(f"  - {DEMO_PRODUCT_COUNT} products")
    print(f"  - {DEMO_CLIENT_COUNT} clients")


if __name__ == "__main__":
    asyncio.run(main())
