"""Demo seed: 1 admin, 1 seller, 50 products, 50 clients, 2 taxes.

Idempotent: looks up by unique key (email, name) before inserting.
"""

from __future__ import annotations

import random
from decimal import Decimal
from typing import Any

from sqlalchemy import select

from app.config import get_settings
from app.core.security import hash_password
from app.infrastructure.db.models.client import Client
from app.infrastructure.db.models.product import Product
from app.infrastructure.db.models.role import Role
from app.infrastructure.db.models.tax import Tax
from app.infrastructure.db.models.user import User
from app.infrastructure.db.models.user_role import UserRole
from app.infrastructure.db.session import init_engine, sync_session_scope

DEMO_USERS = [
    {
        "username": "admin",
        "name": "Ada",
        "last_name": "Admin",
        "email": "admin@example.com",
        "password": "Admin123!",
        "cedula": "1712345678",
    },
    {
        "username": "seller",
        "name": "Sol",
        "last_name": "Vendedora",
        "email": "seller@example.com",
        "password": "Seller123!",
        "cedula": "1798765432",
    },
]

DEMO_TAXES: list[dict[str, Any]] = [
    {"name": "IVA 0%", "current_rate": Decimal("0.00")},
    {"name": "IVA 5%", "current_rate": Decimal("5.00")},
    {"name": "IVA 12%", "current_rate": Decimal("12.00")},
    {"name": "IVA 14%", "current_rate": Decimal("14.00")},
    {"name": "IVA 15%", "current_rate": Decimal("15.00")},
]

DEMO_PRODUCT_COUNT = 50
DEMO_CLIENT_COUNT = 50


def _ensure_role(session, name: str) -> Role:
    existing = session.execute(select(Role).where(Role.name == name)).scalar_one_or_none()
    if existing:
        return existing
    role = Role(name=name, description=name.title())
    session.add(role)
    session.flush()
    return role


def _ensure_user(session, role: Role, spec: dict) -> User:
    existing = session.execute(select(User).where(User.email == spec["email"])).scalar_one_or_none()
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
    session.flush()
    session.add(UserRole(user_id=user.id, role_id=role.id))
    return user


def _ensure_tax(session, spec: dict) -> Tax:
    existing = session.execute(select(Tax).where(Tax.name == spec["name"])).scalar_one_or_none()
    if existing:
        return existing
    tax = Tax(name=spec["name"], current_rate=spec["current_rate"])
    session.add(tax)
    session.flush()
    return tax


def _ensure_product(session, name: str, price: Decimal, stock: int) -> Product:
    existing = session.execute(select(Product).where(Product.name == name)).scalar_one_or_none()
    if existing:
        return existing
    product = Product(name=name, price=price, stock=stock, is_active=True)
    session.add(product)
    session.flush()
    return product


def _ensure_client(session, first: str, last: str, email: str) -> Client:
    existing = session.execute(select(Client).where(Client.email == email)).scalar_one_or_none()
    if existing:
        return existing
    client = Client(first_name=first, last_name=last, email=email, is_active=True)
    session.add(client)
    session.flush()
    return client


def main() -> None:
    settings = get_settings()
    init_engine(settings.database_url_sync)
    rng = random.Random(42)

    with sync_session_scope() as session:
        admin_role = _ensure_role(session, "ADMINISTRATOR")
        seller_role = _ensure_role(session, "SELLER")
        for spec in DEMO_USERS:
            role = admin_role if "admin" in spec["username"] else seller_role
            _ensure_user(session, role, spec)

        for spec in DEMO_TAXES:
            _ensure_tax(session, spec)

        for i in range(1, DEMO_PRODUCT_COUNT + 1):
            name = f"Producto {i:03d}"
            price = Decimal(rng.randint(50, 9999)) / Decimal("100")
            stock = rng.randint(0, 200)
            _ensure_product(session, name, price, stock)

        for i in range(1, DEMO_CLIENT_COUNT + 1):
            first = f"Cliente{i:03d}"
            last = "Demo"
            email = f"cliente{i:03d}@example.com"
            _ensure_client(session, first, last, email)

    print("Demo seed complete.")
    print("  - 2 users (admin@example.com, seller@example.com)")
    print(f"  - {len(DEMO_TAXES)} taxes")
    print(f"  - {DEMO_PRODUCT_COUNT} products")
    print(f"  - {DEMO_CLIENT_COUNT} clients")


if __name__ == "__main__":
    main()
