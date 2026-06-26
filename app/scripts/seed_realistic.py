"""Realistic seed for the POS rebuild.

Inspired by Proyecto_A/pos-api's prisma/seed.ts. Uses the same
name pools so the two systems stay visually consistent, plus a
more product-aware catalog (grocery + electronics + household,
grouped by category, with realistic Ecuador prices in USD).

Generates:
  - 2 roles: ADMINISTRATOR, SELLER.
  - 2 stable demo users: admin@example.com, seller@example.com.
  - ~98 extra users with realistic Ecuador first/last names and
    module-10-valid cédulas.
  - 2 taxes: IVA 15%, IVA 0%.
  - ~120 products across 8 categories, with realistic prices and
    stock levels.
  - ~120 clients with names, addresses, and module-10-valid cédulas.

Deterministic via a fixed random seed (mulberry32 port), so the
dataset is reproducible.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from sqlalchemy import select

from app.config import get_settings
from app.core.security import hash_password
from app.infrastructure.db.models import (
    Client,
    Product,
    Role,
    Tax,
    User,
    UserRole,
)
from app.infrastructure.db.session import get_session_factory, init_engine

# ---------------------------------------------------------------------------
# Deterministic RNG (mulberry32, matches Proyecto_A/pos-api).
# ---------------------------------------------------------------------------


class _Rng:
    """mulberry32 — same algorithm as the original seed.ts."""

    def __init__(self, seed: int) -> None:
        self._s = seed & 0xFFFFFFFF

    def next(self) -> float:
        self._s = (self._s + 0x6D2B79F5) & 0xFFFFFFFF
        t = self._s
        t = ((t ^ (t >> 15)) * (1 | t)) & 0xFFFFFFFF
        t = (t + ((t ^ (t >> 7)) * (61 | t))) & 0xFFFFFFFF
        t = t ^ (t << 14)
        return ((t ^ (t >> 18)) >> 0) / 4294967296

    def int_range(self, lo: int, hi: int) -> int:
        return int(self.next() * (hi - lo + 1)) + lo

    def float_range(self, lo: float, hi: float, decimals: int = 2) -> Decimal:
        v = self.next() * (hi - lo) + lo
        q = Decimal(10) ** -decimals
        return (Decimal(str(v)) / q).quantize(q) * q / q * q  # noqa

    def pick(self, items: list) -> Any:
        return items[self.int_range(0, len(items) - 1)]

    def shuffle(self, items: list) -> list:
        out = list(items)
        for i in range(len(out) - 1, 0, -1):
            j = self.int_range(0, i)
            out[i], out[j] = out[j], out[i]
        return out


rng = _Rng(20260608)


# ---------------------------------------------------------------------------
# Name pools (ported from Proyecto_A/pos-api/prisma/seed.ts).
# ---------------------------------------------------------------------------

FIRST_NAMES: list[str] = [
    "Juan",
    "María",
    "Carlos",
    "Ana",
    "Pedro",
    "Laura",
    "Diego",
    "Sofía",
    "Martín",
    "Valentina",
    "Lucas",
    "Camila",
    "Sebastián",
    "Isabella",
    "Mateo",
    "Lucía",
    "Nicolás",
    "Victoria",
    "Joaquín",
    "Martina",
    "Benjamín",
    "Catalina",
    "Thiago",
    "Renata",
    "Gael",
    "Emilia",
    "Santiago",
    "Josefina",
    "Bautista",
    "Mía",
]

LAST_NAMES: list[str] = [
    "Pérez",
    "García",
    "Rodríguez",
    "Martínez",
    "Sánchez",
    "López",
    "Fernández",
    "Gómez",
    "Torres",
    "Díaz",
    "Ruiz",
    "Romero",
    "Alvarez",
    "Moreno",
    "Gutiérrez",
    "González",
    "Hernández",
    "Jiménez",
    "Ramos",
    "Vázquez",
    "Domínguez",
    "Castro",
    "Suárez",
    "Molina",
    "Delgado",
    "Iglesias",
    "Cortés",
    "Ortiz",
    "Marín",
    "Castillo",
]

# ---------------------------------------------------------------------------
# Product catalog (POS-friendly, not the electronics-heavy list from
# Proyecto_A which doesn't fit a "supermercado pequeño").
# ---------------------------------------------------------------------------

PRODUCT_CATALOG: list[tuple[str, str, str, tuple[float, float]]] = [
    # (name, category, unit_label, (min_price, max_price))
    # Bebidas
    ("Coca-Cola 1.5L", "Bebidas", "Botella 1.5L", (1.50, 2.20)),
    ("Coca-Cola 600ml", "Bebidas", "Botella 600ml", (0.70, 1.10)),
    ("Sprite 1.5L", "Bebidas", "Botella 1.5L", (1.40, 2.00)),
    ("Fanta Naranja 1.5L", "Bebidas", "Botella 1.5L", (1.40, 2.00)),
    ("Agua Mineral 1L", "Bebidas", "Botella 1L", (0.40, 0.80)),
    ("Cerveza Pilsener 6-pack", "Bebidas", "Pack 6x355ml", (4.50, 6.50)),
    ("Cerveza Club 6-pack", "Bebidas", "Pack 6x355ml", (4.20, 6.00)),
    ("Jugo del Valle 1L", "Bebidas", "Botella 1L", (1.20, 1.80)),
    ("Agua con gas 500ml", "Bebidas", "Botella 500ml", (0.50, 0.90)),
    ("Energizante Red Bull 250ml", "Bebidas", "Lata 250ml", (1.80, 2.50)),
    # Panadería
    ("Pan Bimbo Integral 500g", "Panadería", "Bolsa 500g", (1.80, 2.50)),
    ("Pan Bimbo Blanco 500g", "Panadería", "Bolsa 500g", (1.60, 2.30)),
    ("Croissant Donut 6-pack", "Panadería", "Bolsa x6", (2.50, 3.80)),
    ("Tostadas Integrales 200g", "Panadería", "Bolsa 200g", (1.20, 1.80)),
    ("Galletas Club Social 6-pack", "Panadería", "Caja x6", (1.80, 2.60)),
    ("Empanada de Carne", "Panadería", "Unidad", (0.80, 1.50)),
    ("Croissant de Mantequilla", "Panadería", "Unidad", (0.90, 1.60)),
    # Lácteos
    ("Leche Parmalat 1L", "Lácteos", "Caja 1L", (1.10, 1.50)),
    ("Leche Toni 1L", "Lácteos", "Caja 1L", (1.00, 1.40)),
    ("Yogurt Toni Fresa 1L", "Lácteos", "Botella 1L", (1.80, 2.50)),
    ("Queso Fresco 500g", "Lácteos", "Bloque 500g", (2.50, 4.20)),
    ("Mantequilla La Vaquita 250g", "Lácteos", "Barra 250g", (1.80, 2.80)),
    ("Queso Crema Danone 200g", "Lácteos", "Pote 200g", (1.50, 2.20)),
    ("Yogurt Activia Natural 120g", "Lácteos", "Pote 120g", (0.80, 1.30)),
    # Carnes
    ("Pechuga de Pollo 1kg", "Carnes", "Empaque 1kg", (4.50, 6.50)),
    ("Carne Molida 500g", "Carnes", "Empaque 500g", (3.20, 4.80)),
    ("Costilla de Cerdo 1kg", "Carnes", "Empaque 1kg", (4.20, 6.00)),
    ("Salchicha Plumrose 500g", "Carnes", "Empaque 500g", (2.20, 3.50)),
    ("Atún en Lata Isabel 170g", "Carnes", "Lata 170g", (1.50, 2.30)),
    ("Chorizo Parrillero 500g", "Carnes", "Empaque 500g", (3.50, 5.20)),
    # Frutas y Verduras
    ("Banano Maduro 1kg", "Frutas y Verduras", "Bolsa 1kg", (0.60, 1.20)),
    ("Manzana Roja 1kg", "Frutas y Verduras", "Bolsa 1kg", (1.80, 2.80)),
    ("Naranja 1kg", "Frutas y Verduras", "Bolsa 1kg", (0.80, 1.50)),
    ("Tomate Riñón 1kg", "Frutas y Verduras", "Bolsa 1kg", (1.20, 2.00)),
    ("Cebolla Blanca 1kg", "Frutas y Verduras", "Bolsa 1kg", (0.80, 1.40)),
    ("Papa Superchola 1kg", "Frutas y Verduras", "Bolsa 1kg", (0.90, 1.50)),
    ("Zanahoria 1kg", "Frutas y Verduras", "Bolsa 1kg", (0.70, 1.20)),
    ("Plátano Verde 1kg", "Frutas y Verduras", "Bolsa 1kg", (0.60, 1.10)),
    ("Papa Lavada 1kg", "Frutas y Verduras", "Bolsa 1kg", (1.00, 1.60)),
    ("Cebolla Paiteña 1kg", "Frutas y Verduras", "Bolsa 1kg", (0.90, 1.50)),
    # Abarrotes
    ("Arroz Pilado 1kg", "Abarrotes", "Bolsa 1kg", (0.90, 1.40)),
    ("Azúcar Valdez 1kg", "Abarrotes", "Bolsa 1kg", (0.95, 1.50)),
    ("Aceite Girasol 1L", "Abarrotes", "Botella 1L", (2.20, 3.20)),
    ("Fideos Don Vittorio 500g", "Abarrotes", "Bolsa 500g", (0.80, 1.30)),
    ("Atún Van Camps 170g", "Abarrotes", "Lata 170g", (1.40, 2.10)),
    ("Salsa de Tomate Don Vittorio 200g", "Abarrotes", "Sobre 200g", (0.60, 1.00)),
    ("Sal Yodada 1kg", "Abarrotes", "Bolsa 1kg", (0.40, 0.80)),
    ("Lenteja 500g", "Abarrotes", "Bolsa 500g", (1.20, 1.80)),
    ("Arveja Seca 500g", "Abarrotes", "Bolsa 500g", (1.30, 2.00)),
    ("Avena en Hojuelas 500g", "Abarrotes", "Bolsa 500g", (1.20, 1.80)),
    # Limpieza
    ("Detergente Fab 1kg", "Limpieza", "Bolsa 1kg", (2.20, 3.20)),
    ("Jabón Lava Todo Deja 500g", "Limpieza", "Barra 500g", (0.90, 1.40)),
    ("Cloro Magia Blanca 1L", "Limpieza", "Botella 1L", (1.20, 1.80)),
    ("Papel Higiénico Familia 4-pack", "Limpieza", "Pack x4", (1.80, 2.80)),
    ("Lavavajillas Axion 500g", "Limpieza", "Pote 500g", (1.40, 2.20)),
    ("Desinfectante Lysol 1L", "Limpieza", "Botella 1L", (2.50, 3.50)),
    ("Esponja Scotch-Brite 3-pack", "Limpieza", "Pack x3", (0.80, 1.40)),
    # Cuidado personal
    ("Shampoo Head & Shoulders 400ml", "Cuidado Personal", "Frasco 400ml", (3.20, 4.80)),
    ("Jabón Palmolive 3-pack", "Cuidado Personal", "Pack x3", (1.80, 2.80)),
    ("Pasta Dental Colgate 100g", "Cuidado Personal", "Tubo 100g", (1.20, 1.90)),
    ("Desodorante Rexona 150ml", "Cuidado Personal", "Tubo 150ml", (2.50, 3.80)),
    ("Papel Higiénico Familia 12-rollos", "Cuidado Personal", "Pack x12", (4.20, 6.50)),
    ("Cepillo Dental Colgate", "Cuidado Personal", "Unidad", (0.80, 1.50)),
    ("Acondicionador Sedal 350ml", "Cuidado Personal", "Frasco 350ml", (2.80, 4.20)),
    # Snacks
    ("Papas Pringles Original 124g", "Snacks", "Tubo 124g", (2.50, 3.80)),
    ("Doritos Queso 200g", "Snacks", "Bolsa 200g", (1.80, 2.80)),
    ("Cheetos Torciditos 150g", "Snacks", "Bolsa 150g", (1.20, 2.00)),
    ("Maní Salado 200g", "Snacks", "Bolsa 200g", (1.20, 1.80)),
    ("Chicles Trident 12-pack", "Snacks", "Caja x12", (1.20, 1.80)),
    ("Chocolate Nestlé 100g", "Snacks", "Barra 100g", (0.90, 1.50)),
    ("Galletas Oreo 6-pack", "Snacks", "Pack x6", (1.80, 2.60)),
    # Hogar
    ("Servilletas Familia 100-hojas", "Hogar", "Paquete 100", (0.80, 1.40)),
    ("Bolsas de Basura 30L 10-pack", "Hogar", "Paquete x10", (1.20, 1.90)),
    ("Film Adherente 100m", "Hogar", "Rollo 100m", (2.20, 3.20)),
    ("Papel Aluminio 30m", "Hogar", "Rollo 30m", (2.50, 3.80)),
    ("Fósforos 50 unidades", "Hogar", "Caja x50", (0.40, 0.80)),
    ("Velas 6-pack", "Hogar", "Pack x6", (1.50, 2.20)),
    # Mascotas
    ("Alimento Dog Chow 1kg", "Mascotas", "Bolsa 1kg", (2.80, 4.20)),
    ("Alimento Whiskas Gato 500g", "Mascotas", "Bolsa 500g", (2.50, 3.80)),
    ("Alimento Dog Chow Cachorro 1kg", "Mascotas", "Bolsa 1kg", (3.20, 4.80)),
    # Electrónica (pocos, porque es un minimercado)
    ("Pilas AA Duracell 4-pack", "Electrónica", "Pack x4", (2.80, 4.20)),
    ("Pilas AAA Duracell 4-pack", "Electrónica", "Pack x4", (2.50, 3.80)),
    ("Foco LED 9W", "Electrónica", "Unidad", (1.20, 2.00)),
    ("Cargador USB-C 20W", "Electrónica", "Unidad", (3.20, 4.80)),
]


# ---------------------------------------------------------------------------
# Helpers.
# ---------------------------------------------------------------------------


def _generate_cedula() -> str:
    """Ecuadorian cédula, modulo 10 (matches the validator)."""
    # 95% provinces 01-24, 5% province 30 (foreigners).
    province = f"{rng.int_range(1, 24):02d}" if rng.next() < 0.95 else "30"
    third = str(rng.int_range(0, 5))
    rest = "".join(str(rng.int_range(0, 9)) for _ in range(6))
    nine = province + third + rest
    digits = [int(c) for c in nine]
    coeffs = [2, 1, 2, 1, 2, 1, 2, 1, 2]
    total = 0
    for d, c in zip(digits, coeffs, strict=True):
        prod = d * c
        total += prod - 9 if prod >= 10 else prod
    check = (10 - (total % 10)) % 10
    return nine + str(check)


def _slug(s: str) -> str:
    """ASCII slug for usernames (lowercase, no accents)."""
    out = []
    for ch in s.lower():
        if ch.isascii() and ch.isalnum():
            out.append(ch)
    return "".join(out)


def _user_password_for(role: str) -> str:
    return "Admin123!" if role == "ADMINISTRATOR" else "Seller123!"


# ---------------------------------------------------------------------------
# Main seed.
# ---------------------------------------------------------------------------


async def seed() -> None:
    factory = get_session_factory()

    # Roles
    async with factory() as s:
        for name, code in [("ADMINISTRATOR", "ADMIN"), ("SELLER", "SELL")]:
            if (
                await s.execute(select(Role).where(Role.name == name))
            ).scalar_one_or_none() is None:
                s.add(Role(name=name, code=code))
        await s.commit()

    # Taxes
    async with factory() as s:
        for name, rate in [
            ("IVA 0%", Decimal("0.00")),
            ("IVA 5%", Decimal("5.00")),
            ("IVA 12%", Decimal("12.00")),
            ("IVA 14%", Decimal("14.00")),
            ("IVA 15%", Decimal("15.00")),
        ]:
            found_tax = (await s.execute(select(Tax).where(Tax.name == name))).scalar_one_or_none()
            if found_tax is None:
                s.add(Tax(name=name, current_rate=rate))
        await s.commit()

    # Demo users (id 1 = admin, id 2 = seller; stable for login).
    async with factory() as s:
        admin_email = "admin@example.com"
        seller_email = "seller@example.com"
        admin_role = (
            await s.execute(select(Role).where(Role.name == "ADMINISTRATOR"))
        ).scalar_one()
        seller_role = (await s.execute(select(Role).where(Role.name == "SELLER"))).scalar_one()

        for email, name, last, role in [
            (admin_email, "Admin", "POS", admin_role),
            (seller_email, "Seller", "POS", seller_role),
        ]:
            found_user = (
                await s.execute(select(User).where(User.email == email))
            ).scalar_one_or_none()
            if found_user is None:
                user = User(
                    username=email.split("@")[0],
                    email=email,
                    password=hash_password(_user_password_for(role.name)),
                    name=name,
                    last_name=last,
                )
                s.add(user)
                await s.flush()
                s.add(UserRole(user_id=user.id, role_id=role.id))
        await s.commit()

    # Products (~120 from the catalog).
    async with factory() as s:
        existing_count = (await s.execute(select(Product))).scalars().all()
        if len(existing_count) >= 50:
            return  # already seeded

        for name, category, unit, (lo, hi) in PRODUCT_CATALOG:
            price = Decimal(str(round(rng.next() * (hi - lo) + lo, 2)))
            stock = rng.int_range(10, 80)
            sku = f"{category[:3].upper()}-{rng.int_range(1000, 9999)}"
            if (
                await s.execute(select(Product).where(Product.name == name))
            ).scalar_one_or_none() is None:
                s.add(
                    Product(
                        name=name,
                        sku=sku,
                        category=category,
                        unit=unit,
                        price=price,
                        stock=stock,
                        is_active=True,
                    )
                )
        await s.commit()

    # Clients (~120, with realistic Ecuador names + module-10 cedulas).
    async with factory() as s:
        existing_clients = (await s.execute(select(Client))).scalars().all()
        if len(existing_clients) >= 50:
            return

        streets = [
            "Av. de las Américas",
            "Av. Solanda",
            "Calle García Moreno",
            "Av. Patria",
            "Av. 6 de Diciembre",
            "Calle Bolívar",
            "Av. República",
            "Calle Sucre",
            "Av. Maldonado",
            "Calle Espejo",
        ]
        for _ in range(120):
            cedula = _generate_cedula()
            found_client = (
                await s.execute(select(Client).where(Client.cedula == cedula))
            ).scalar_one_or_none()
            if found_client is not None:
                continue
            first = str(rng.pick(FIRST_NAMES))
            last = str(rng.pick(LAST_NAMES))
            email = f"{_slug(first)}.{_slug(last)}{rng.int_range(10, 99)}@example.com"
            s.add(
                Client(
                    first_name=first,
                    last_name=last,
                    cedula=cedula,
                    email=email,
                    phone=f"09{rng.int_range(10000000, 99999999)}",
                    address=f"{rng.pick(streets)} #{rng.int_range(100, 9999)}",
                )
            )
        await s.commit()


async def main() -> None:
    settings = get_settings()
    init_engine(settings.database_url)
    await seed()
    factory = get_session_factory()
    async with factory() as s:
        users = (await s.execute(select(User))).scalars().all()
        products = (await s.execute(select(Product))).scalars().all()
        clients = (await s.execute(select(Client))).scalars().all()
    print(
        "Realistic seed complete.\n"
        f"  - {len(users)} users (admin@example.com / seller@example.com)\n"
        f"  - {len(products)} products\n"
        f"  - {len(clients)} clients"
    )


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
