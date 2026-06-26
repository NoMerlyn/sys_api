"""Demo seed: 3 admins, 3 sellers, 10,000 products (100 realistic), 10,000 clients (100 realistic),
5 taxes, 20 error logs, 120 historical invoices (with stock audit logs).

Idempotent: wipes all tables before re-seeding.
"""

from __future__ import annotations

import json
import random
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any

from sqlalchemy import select

from app.config import get_settings
from app.core.security import hash_password
from app.infrastructure.db.models.audit_log import AuditLog
from app.infrastructure.db.models.client import Client
from app.infrastructure.db.models.error_log import ErrorLog
from app.infrastructure.db.models.invoice import Invoice, InvoiceStatus, PaymentMethod
from app.infrastructure.db.models.invoice_detail import InvoiceDetail
from app.infrastructure.db.models.product import Product
from app.infrastructure.db.models.role import Role
from app.infrastructure.db.models.tax import Tax
from app.infrastructure.db.models.user import User
from app.infrastructure.db.models.user_role import UserRole
from app.infrastructure.db.session import init_engine, sync_session_scope


def generate_ecuadorian_cedula(prefix: int) -> str:
    seq = f"{prefix:06d}"
    digits = [1, 7, 2] + [int(d) for d in seq]
    coefs = [2, 1, 2, 1, 2, 1, 2, 1, 2]
    total = 0
    for d, c in zip(digits, coefs):
        val = d * c
        if val >= 10:
            val -= 9
        total += val
    checksum = (10 - (total % 10)) % 10
    return f"172{seq}{checksum}"


DEMO_USERS = [
    {
        "username": f"admin{i}",
        "name": ["Ada", "Beto", "Clara"][i - 1],
        "last_name": f"Admin {['Uno', 'Dos', 'Tres'][i - 1]}",
        "email": f"admin{i}@example.com",
        "password": "Admin123!",
        "cedula": generate_ecuadorian_cedula(1000 + i),
    }
    for i in range(1, 4)
] + [
    {
        "username": f"seller{i}",
        "name": ["Sol", "Luna", "Estrella"][i - 1],
        "last_name": f"Vendedor {['Uno', 'Dos', 'Tres'][i - 1]}",
        "email": f"seller{i}@example.com",
        "password": "Seller123!",
        "cedula": generate_ecuadorian_cedula(2000 + i),
    }
    for i in range(1, 4)
]

DEMO_TAXES: list[dict[str, Any]] = [
    {"name": "IVA 0%", "current_rate": Decimal("0.00")},
    {"name": "IVA 5%", "current_rate": Decimal("5.00")},
    {"name": "IVA 12%", "current_rate": Decimal("12.00")},
    {"name": "IVA 14%", "current_rate": Decimal("14.00")},
    {"name": "IVA 15%", "current_rate": Decimal("15.00")},
]

FIRST_NAMES = [
    "Juan", "María", "Carlos", "Ana", "Pedro", "Laura", "Diego", "Sofía", "Martín", "Valentina",
    "Lucas", "Camila", "Sebastián", "Isabella", "Mateo", "Lucía", "Nicolás", "Victoria", "Joaquín",
    "Martina", "Benjamín", "Catalina", "Thiago", "Renata", "Gael", "Emilia", "Santiago", "Josefina",
    "Bautista", "Mía",
]

LAST_NAMES = [
    "Pérez", "García", "Rodríguez", "Martínez", "Sánchez", "López", "Fernández", "Gómez", "Torres",
    "Díaz", "Ruiz", "Romero", "Alvarez", "Moreno", "Gutiérrez", "González", "Hernández", "Jiménez",
    "Ramos", "Vázquez", "Domínguez", "Castro", "Suárez", "Molina", "Delgado", "Iglesias", "Cortés",
    "Ortiz", "Marín", "Castillo",
]

REALISTIC_PRODUCTS = [
    ("Leche Entera 1L", Decimal("1.20"), 500),
    ("Leche Deslactosada 1L", Decimal("1.40"), 400),
    ("Queso Mozzarella 500g", Decimal("4.50"), 300),
    ("Queso Fresco 500g", Decimal("3.20"), 350),
    ("Mantequilla con Sal 250g", Decimal("2.10"), 450),
    ("Yogurt de Fresa 1L", Decimal("2.40"), 350),
    ("Yogurt de Durazno 1L", Decimal("2.40"), 300),
    ("Yogurt Natural 120g", Decimal("0.85"), 600),
    ("Crema de Leche 200ml", Decimal("1.30"), 500),
    ("Pan Molde Blanco 500g", Decimal("1.80"), 400),
    ("Pan Molde Integral 500g", Decimal("2.20"), 350),
    ("Pan de Hamburguesa 4-pack", Decimal("1.50"), 300),
    ("Pan de Hotdog 6-pack", Decimal("1.40"), 280),
    ("Galletas de Sal Pack", Decimal("1.90"), 500),
    ("Galletas de Chocolate", Decimal("0.60"), 700),
    ("Galletas Chocochips", Decimal("1.20"), 600),
    ("Arroz Super Extra 1kg", Decimal("1.30"), 800),
    ("Arroz Extra 5kg", Decimal("6.20"), 500),
    ("Azúcar Blanca 1kg", Decimal("1.10"), 700),
    ("Azúcar Morena 1kg", Decimal("1.25"), 550),
    ("Aceite de Girasol 1L", Decimal("2.90"), 450),
    ("Aceite de Oliva Extra Virgen 500ml", Decimal("6.80"), 300),
    ("Sal Yodada 1kg", Decimal("0.45"), 900),
    ("Fideos Tallarín 500g", Decimal("0.85"), 650),
    ("Fideos Macarrón 500g", Decimal("0.85"), 600),
    ("Atún en Aceite 170g", Decimal("1.80"), 800),
    ("Atún en Agua 170g", Decimal("1.70"), 750),
    ("Salsa de Tomate 400g", Decimal("1.40"), 550),
    ("Mayonesa Doypack 400g", Decimal("1.95"), 500),
    ("Mostaza Doypack 200g", Decimal("0.95"), 480),
    ("Café Instantáneo 100g", Decimal("3.50"), 400),
    ("Café Molido 250g", Decimal("4.20"), 350),
    ("Té Negro 20 bolsitas", Decimal("1.10"), 500),
    ("Té Verde 20 bolsitas", Decimal("1.40"), 450),
    ("Cocoa en Polvo 200g", Decimal("2.10"), 380),
    ("Coca-Cola 1.5L", Decimal("1.85"), 800),
    ("Coca-Cola 3L", Decimal("3.10"), 600),
    ("Sprite 1.5L", Decimal("1.65"), 550),
    ("Fanta 1.5L", Decimal("1.65"), 520),
    ("Jugo de Naranja 1L", Decimal("1.80"), 450),
    ("Jugo de Manzana 1L", Decimal("1.80"), 420),
    ("Agua Sin Gas 1.5L", Decimal("0.75"), 900),
    ("Agua Con Gas 1.5L", Decimal("0.85"), 700),
    ("Energizante 250ml", Decimal("1.50"), 600),
    ("Pechuga de Pollo 1kg", Decimal("5.40"), 400),
    ("Muslo de Pollo 1kg", Decimal("3.80"), 450),
    ("Carne de Res Molida 1kg", Decimal("6.20"), 380),
    ("Lomo de Res 1kg", Decimal("9.50"), 250),
    ("Chuleta de Cerdo 1kg", Decimal("4.80"), 350),
    ("Jamón de Cerdo 200g", Decimal("2.30"), 500),
    ("Mortadela Familiar 200g", Decimal("1.50"), 600),
    ("Salchicha de Pollo 500g", Decimal("2.10"), 480),
    ("Detergente Multiuso 1kg", Decimal("2.80"), 500),
    ("Lavavajillas Líquido 500ml", Decimal("1.60"), 550),
    ("Jabón en Barra Limpieza", Decimal("0.75"), 700),
    ("Cloro Desinfectante 1L", Decimal("1.10"), 600),
    ("Desinfectante Pino 1L", Decimal("1.40"), 580),
    ("Papel Higiénico 4 rollos", Decimal("1.60"), 750),
    ("Papel Higiénico 12 rollos", Decimal("4.50"), 500),
    ("Servilletas de Papel x100", Decimal("0.90"), 650),
    ("Toalla de Cocina 2 rollos", Decimal("1.80"), 520),
    ("Esponja de Cocina x3", Decimal("1.10"), 700),
    ("Shampoo Control Caspa 400ml", Decimal("4.20"), 380),
    ("Acondicionador Brillo 400ml", Decimal("4.20"), 350),
    ("Jabón Líquido Corporal 400ml", Decimal("3.10"), 420),
    ("Jabón en Barra Cuidado x3", Decimal("2.20"), 580),
    ("Pasta Dental Triple Acción", Decimal("1.80"), 620),
    ("Cepillo de Dientes Mediano", Decimal("1.10"), 500),
    ("Desodorante Roll-on 50ml", Decimal("2.90"), 450),
    ("Crema Humectante 200ml", Decimal("3.80"), 350),
    ("Papas Fritas Lisas 150g", Decimal("1.60"), 600),
    ("Doritos Mega Queso 150g", Decimal("1.85"), 580),
    ("Maní Salado Con Sal 150g", Decimal("1.20"), 650),
    ("Pistachos Tostados 100g", Decimal("3.20"), 380),
    ("Chocolate de Leche 100g", Decimal("1.50"), 520),
    ("Chocolate Amargo 70% 80g", Decimal("2.40"), 420),
    ("Manzana Roja Importada 1kg", Decimal("2.80"), 450),
    ("Manzana Verde 1kg", Decimal("3.10"), 400),
    ("Banano Orgánico 1kg", Decimal("0.90"), 700),
    ("Uva Roja Sin Pepilla 1kg", Decimal("4.50"), 300),
    ("Limón Sutil 1kg", Decimal("1.40"), 580),
    ("Naranja de Jugo 1kg", Decimal("1.10"), 650),
    ("Tomate Riñón Calidad 1kg", Decimal("1.80"), 500),
    ("Cebolla Colorada 1kg", Decimal("1.30"), 560),
    ("Papa Chola Seleccionada 1kg", Decimal("1.10"), 750),
    ("Zanahoria Importada 1kg", Decimal("0.95"), 620),
    ("Aguacate Hass 1kg", Decimal("3.50"), 300),
    ("Pimiento Verde 1kg", Decimal("1.60"), 450),
    ("Ajo en Bulbo x3", Decimal("1.00"), 700),
    ("Cangil en Grano 500g", Decimal("0.95"), 600),
    ("Cereal Integral Caja 350g", Decimal("3.80"), 350),
    ("Mermelada de Fresa 350g", Decimal("2.10"), 450),
    ("Miel de Abeja 250g", Decimal("3.90"), 300),
    ("Sardina en Salsa de Tomate", Decimal("1.25"), 750),
    ("Alimento Seco Perro 1.5kg", Decimal("4.80"), 380),
    ("Alimento Seco Gato 1kg", Decimal("4.20"), 420),
    ("Pilas Alcalinas AA x4", Decimal("3.50"), 500),
    ("Pilas Alcalinas AAA x4", Decimal("3.20"), 480),
    ("Foco LED Ahorrador 12W", Decimal("1.80"), 600),
    ("Cargador Rápido USB 18W", Decimal("4.90"), 350),
]

DEMO_PRODUCT_COUNT = 10000
DEMO_CLIENT_COUNT = 10000

# ---------------------------------------------------------------------------
# Error log templates
# ---------------------------------------------------------------------------

ERROR_TEMPLATES = [
    {
        "exception_type": "sqlalchemy.exc.OperationalError",
        "path": "/api/v1/invoices",
        "source": "POST /api/v1/invoices",
        "message": json.dumps({
            "error": "OperationalError",
            "detail": "could not connect to server: Connection refused",
            "hint": "Is the server running on host 'db' (172.18.0.2) and accepting TCP/IP connections on port 5432?",
        }),
        "stack_trace": "Traceback (most recent call last):\n  File \"app/infrastructure/db/session.py\", line 42, in get_session\n    async with AsyncSession(engine) as session:\nsqlalchemy.exc.OperationalError: (psycopg2.OperationalError) could not connect to server",
    },
    {
        "exception_type": "app.core.exceptions.NotFoundError",
        "path": "/api/v1/products/9999",
        "source": "GET /api/v1/products/9999",
        "message": json.dumps({"error": "NotFoundError", "detail": "Producto 9999 no existe"}),
        "stack_trace": "Traceback (most recent call last):\n  File \"app/application/products/handlers.py\", line 88, in handle\n    raise NotFoundError(f'Producto {cmd.product_id} no existe')\napp.core.exceptions.NotFoundError: Producto 9999 no existe",
    },
    {
        "exception_type": "app.core.exceptions.BusinessError",
        "path": "/api/v1/invoices",
        "source": "POST /api/v1/invoices",
        "message": json.dumps({
            "error": "BusinessError",
            "detail": "Stock insuficiente para producto 42",
            "product_id": 42,
            "stock": 0,
            "requested": 5,
        }),
        "stack_trace": "Traceback (most recent call last):\n  File \"app/application/invoices/handlers.py\", line 191, in handle\n    raise BusinessError('Stock insuficiente para producto 42')\napp.core.exceptions.BusinessError: Stock insuficiente para producto 42",
    },
    {
        "exception_type": "pydantic.ValidationError",
        "path": "/api/v1/clients",
        "source": "POST /api/v1/clients",
        "message": json.dumps({
            "error": "ValidationError",
            "detail": [{"loc": ["cedula"], "msg": "cédula inválida", "type": "value_error"}],
        }),
        "stack_trace": "Traceback (most recent call last):\n  File \"app/api/v1/clients.py\", line 31, in create_client\n    dto = CreateClientDto(**body)\npydantic.ValidationError: 1 validation error for CreateClientDto\ncedula\n  cédula inválida (type=value_error)",
    },
    {
        "exception_type": "jose.exceptions.ExpiredSignatureError",
        "path": "/api/v1/auth/me",
        "source": "GET /api/v1/auth/me",
        "message": json.dumps({"error": "ExpiredSignatureError", "detail": "Token has expired"}),
        "stack_trace": "Traceback (most recent call last):\n  File \"app/core/security.py\", line 67, in decode_token\n    payload = jwt.decode(token, settings.secret_key, algorithms=[ALGORITHM])\njose.exceptions.ExpiredSignatureError: Signature has expired.",
    },
    {
        "exception_type": "aio_pika.exceptions.AMQPConnectionError",
        "path": "/api/v1/invoices",
        "source": "POST /api/v1/invoices (RabbitMQ publish)",
        "message": json.dumps({
            "error": "AMQPConnectionError",
            "detail": "Could not connect to RabbitMQ broker at amqp://guest:guest@rabbitmq:5672/",
        }),
        "stack_trace": "Traceback (most recent call last):\n  File \"app/infrastructure/messaging/publishers.py\", line 22, in publish_event\n    channel = await get_channel_pool(url)\naio_pika.exceptions.AMQPConnectionError: Could not connect to RabbitMQ",
    },
    {
        "exception_type": "slowapi.errors.RateLimitExceeded",
        "path": "/api/v1/auth/login",
        "source": "POST /api/v1/auth/login",
        "message": json.dumps({"error": "RateLimitExceeded", "detail": "5 per 1 minute"}),
        "stack_trace": "Traceback (most recent call last):\n  File \"app/api/middleware/rate_limit.py\", line 18, in check_rate_limit\n    raise RateLimitExceeded('5 per 1 minute')\nslowapi.errors.RateLimitExceeded: 5 per 1 minute",
    },
    {
        "exception_type": "UnicodeDecodeError",
        "path": "/api/v1/reports/export",
        "source": "GET /api/v1/reports/export?format=excel",
        "message": json.dumps({
            "error": "UnicodeDecodeError",
            "detail": "'utf-8' codec can't decode byte 0xff in position 0: invalid start byte",
        }),
        "stack_trace": "Traceback (most recent call last):\n  File \"app/application/reports/handlers.py\", line 54, in export_excel\n    data = response.content.decode('utf-8')\nUnicodeDecodeError: 'utf-8' codec can't decode byte 0xff in position 0",
    },
    {
        "exception_type": "asyncio.TimeoutError",
        "path": "/api/v1/invoices/validate",
        "source": "POST /api/v1/invoices/validate (SRI connection)",
        "message": json.dumps({
            "error": "TimeoutError",
            "detail": "Timeout connecting to SRI webservice after 30s",
        }),
        "stack_trace": "Traceback (most recent call last):\n  File \"app/core/sri.py\", line 112, in validate_with_sri\n    response = await asyncio.wait_for(client.post(url, data=xml), timeout=30.0)\nasyncio.TimeoutError",
    },
    {
        "exception_type": "sqlalchemy.exc.IntegrityError",
        "path": "/api/v1/users",
        "source": "POST /api/v1/users",
        "message": json.dumps({
            "error": "IntegrityError",
            "detail": "duplicate key value violates unique constraint 'users_cedula_key'",
            "constraint": "users_cedula_key",
        }),
        "stack_trace": "Traceback (most recent call last):\n  File \"app/application/users/handlers.py\", line 61, in handle\n    await session.flush()\nsqlalchemy.exc.IntegrityError: (psycopg2.errors.UniqueViolation) duplicate key value violates unique constraint 'users_cedula_key'",
    },
    {
        "exception_type": "MemoryError",
        "path": "/api/v1/reports/export",
        "source": "GET /api/v1/reports/export?format=excel&range=all",
        "message": json.dumps({
            "error": "MemoryError",
            "detail": "Ran out of memory while generating Excel report with 50,000 rows",
        }),
        "stack_trace": "Traceback (most recent call last):\n  File \"app/application/reports/handlers.py\", line 88, in export_excel\n    wb = openpyxl.Workbook()\nMemoryError",
    },
    {
        "exception_type": "app.core.exceptions.BusinessError",
        "path": "/api/v1/invoices/45/status",
        "source": "PATCH /api/v1/invoices/45/status",
        "message": json.dumps({
            "error": "BusinessError",
            "detail": "Transición no permitida: CONFIRMED -> PENDING_VALIDATION",
        }),
        "stack_trace": "Traceback (most recent call last):\n  File \"app/application/invoices/handlers.py\", line 577, in handle\n    raise BusinessError(f'Transición no permitida: {inv.status} -> {target}')\napp.core.exceptions.BusinessError: Transición no permitida: CONFIRMED -> PENDING_VALIDATION",
    },
    {
        "exception_type": "httpx.ConnectTimeout",
        "path": "/api/v1/invoices/xml/10",
        "source": "GET /api/v1/invoices/xml/10 (SRI submission)",
        "message": json.dumps({
            "error": "ConnectTimeout",
            "detail": "HTTPSConnectionPool(host='celcer.sri.gob.ec', port=443): Read timed out. (read timeout=10)",
        }),
        "stack_trace": "Traceback (most recent call last):\n  File \"app/core/sri.py\", line 144, in submit_to_sri\n    resp = await client.post(SRI_RECEPTION_URL, content=signed_xml)\nhttpx.ConnectTimeout: HTTPSConnectionPool(host='celcer.sri.gob.ec', port=443)",
    },
    {
        "exception_type": "KeyError",
        "path": "/api/v1/invoices",
        "source": "POST /api/v1/invoices (payload parsing)",
        "message": json.dumps({
            "error": "KeyError",
            "detail": "'items'",
            "hint": "Request body is missing required field 'items'",
        }),
        "stack_trace": "Traceback (most recent call last):\n  File \"app/api/v1/invoices.py\", line 28, in create_invoice\n    items = body['items']\nKeyError: 'items'",
    },
    {
        "exception_type": "ZeroDivisionError",
        "path": "/api/v1/reports/summary",
        "source": "GET /api/v1/reports/summary",
        "message": json.dumps({
            "error": "ZeroDivisionError",
            "detail": "division by zero while computing average ticket (no invoices found for period)",
        }),
        "stack_trace": "Traceback (most recent call last):\n  File \"app/application/reports/handlers.py\", line 67, in compute_summary\n    avg_ticket = total_revenue / invoice_count\nZeroDivisionError: division by zero",
    },
    {
        "exception_type": "sqlalchemy.exc.OperationalError",
        "path": "/api/v1/products",
        "source": "GET /api/v1/products (bulk query)",
        "message": json.dumps({
            "error": "OperationalError",
            "detail": "SSL connection has been closed unexpectedly",
        }),
        "stack_trace": "Traceback (most recent call last):\n  File \"app/infrastructure/repositories/product_repository.py\", line 44, in find_all\n    result = await session.execute(stmt)\nsqlalchemy.exc.OperationalError: SSL connection has been closed unexpectedly",
    },
    {
        "exception_type": "app.core.exceptions.UnauthorizedError",
        "path": "/api/v1/users/2",
        "source": "DELETE /api/v1/users/2",
        "message": json.dumps({
            "error": "UnauthorizedError",
            "detail": "Solo administradores pueden eliminar usuarios",
        }),
        "stack_trace": "Traceback (most recent call last):\n  File \"app/application/users/handlers.py\", line 155, in handle\n    raise UnauthorizedError('Solo administradores pueden eliminar usuarios')\napp.core.exceptions.UnauthorizedError: Solo administradores pueden eliminar usuarios",
    },
    {
        "exception_type": "ValueError",
        "path": "/api/v1/taxes",
        "source": "POST /api/v1/taxes",
        "message": json.dumps({
            "error": "ValueError",
            "detail": "current_rate must be between 0 and 100, got: 150.5",
        }),
        "stack_trace": "Traceback (most recent call last):\n  File \"app/application/taxes/handlers.py\", line 44, in handle\n    raise ValueError(f'current_rate must be between 0 and 100, got: {dto.current_rate}')\nValueError: current_rate must be between 0 and 100, got: 150.5",
    },
    {
        "exception_type": "asyncio.CancelledError",
        "path": "/api/v1/invoices/bulk",
        "source": "POST /api/v1/invoices/bulk (worker task cancelled)",
        "message": json.dumps({
            "error": "CancelledError",
            "detail": "Background task was cancelled during bulk invoice creation (worker restart?)",
        }),
        "stack_trace": "Traceback (most recent call last):\n  File \"app/application/invoices/handlers.py\", line 390, in handle\n    await asyncio.sleep(2.0)\nasyncio.CancelledError",
    },
    {
        "exception_type": "FileNotFoundError",
        "path": "/api/v1/invoices/pdf/88",
        "source": "GET /api/v1/invoices/pdf/88",
        "message": json.dumps({
            "error": "FileNotFoundError",
            "detail": "No such file or directory: '/app/tmp/invoices/invoice_88.pdf'",
        }),
        "stack_trace": "Traceback (most recent call last):\n  File \"app/api/v1/invoices.py\", line 72, in get_invoice_pdf\n    with open(pdf_path, 'rb') as f:\nFileNotFoundError: [Errno 2] No such file or directory: '/app/tmp/invoices/invoice_88.pdf'",
    },
]


def clear_database(session) -> None:
    from sqlalchemy import delete

    from app.infrastructure.db.models.blocked_user import BlockedUser
    from app.infrastructure.db.models.invoice_detail_tax import InvoiceDetailTax
    from app.infrastructure.db.models.processed_event import ProcessedEvent
    from app.infrastructure.db.models.product_tax import ProductTax
    from app.infrastructure.db.models.refresh_token import RefreshToken
    from app.infrastructure.db.models.stock_movement import StockMovement

    session.execute(delete(UserRole))
    session.execute(delete(InvoiceDetailTax))
    session.execute(delete(InvoiceDetail))
    session.execute(delete(Invoice))
    session.execute(delete(StockMovement))
    session.execute(delete(ProductTax))
    session.execute(delete(RefreshToken))
    session.execute(delete(BlockedUser))
    session.execute(delete(AuditLog))
    session.execute(delete(ErrorLog))
    session.execute(delete(ProcessedEvent))

    session.execute(delete(User))
    session.execute(delete(Client))
    session.execute(delete(Product))
    session.execute(delete(Tax))
    session.execute(delete(Role))
    session.flush()


def _ensure_role(session, name: str) -> Role:
    existing = session.execute(select(Role).where(Role.name == name)).scalar_one_or_none()
    if existing:
        return existing
    role = Role(name=name, description=name.title())
    session.add(role)
    session.flush()
    return role


def _q(v: Decimal) -> Decimal:
    from decimal import ROUND_HALF_UP
    return v.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def main() -> None:
    settings = get_settings()
    init_engine(settings.database_url_sync)
    rng = random.Random(42)
    now = datetime.now(tz=timezone.utc)

    with sync_session_scope() as session:
        print("Clearing existing database tables...")
        clear_database(session)

        print("Seeding roles and users...")
        admin_role = _ensure_role(session, "ADMINISTRATOR")
        seller_role = _ensure_role(session, "SELLER")

        seeded_users: list[User] = []
        seeded_sellers: list[User] = []
        for spec in DEMO_USERS:
            role = admin_role if "admin" in spec["username"] else seller_role
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
            seeded_users.append(user)
            if "seller" in spec["username"]:
                seeded_sellers.append(user)

        print("Seeding taxes...")
        seeded_taxes: list[Tax] = []
        for spec in DEMO_TAXES:
            tax = Tax(name=spec["name"], current_rate=spec["current_rate"])
            session.add(tax)
            seeded_taxes.append(tax)
        session.flush()

        print("Generating 10,000 products...")
        product_dicts = []
        # First 100 realistic (with higher stock to survive historical invoices)
        for name, price, stock in REALISTIC_PRODUCTS:
            product_dicts.append({
                "name": name,
                "price": price,
                "stock": stock,
                "is_active": True,
                "version": 0,
            })
        # Remaining 9,900 mock
        for i in range(101, DEMO_PRODUCT_COUNT + 1):
            product_dicts.append({
                "name": f"Producto Falso {i:05d}",
                "price": Decimal(rng.randint(50, 9999)) / Decimal("100"),
                "stock": rng.randint(50, 500),
                "is_active": True,
                "version": 0,
            })
        session.bulk_insert_mappings(Product, product_dicts)
        session.flush()

        # Re-fetch first 100 products for invoice generation
        from sqlalchemy import asc
        all_products = session.execute(
            select(Product).where(Product.is_active.is_(True)).order_by(asc(Product.id)).limit(100)
        ).scalars().all()

        print("Generating 10,000 clients...")
        client_dicts = []
        for i in range(1, 101):
            first = FIRST_NAMES[(i - 1) % len(FIRST_NAMES)]
            last = LAST_NAMES[((i - 1) * 3) % len(LAST_NAMES)]
            email = f"{first.lower()}.{last.lower()}{i}@example.com"
            cedula = generate_ecuadorian_cedula(3000 + i)
            client_dicts.append({
                "first_name": first,
                "last_name": last,
                "email": email,
                "cedula": cedula,
                "is_active": True,
            })
        for i in range(101, DEMO_CLIENT_COUNT + 1):
            client_dicts.append({
                "first_name": f"Cliente{i:05d}",
                "last_name": "Fake",
                "email": f"cliente{i}@falso.com",
                "cedula": generate_ecuadorian_cedula(4000 + i),
                "is_active": True,
            })
        session.bulk_insert_mappings(Client, client_dicts)
        session.flush()

        # Re-fetch first 100 clients
        all_clients = session.execute(
            select(Client).where(Client.is_active.is_(True)).order_by(asc(Client.id)).limit(100)
        ).scalars().all()

        # -----------------------------------------------------------------------
        # 20 Error logs distributed over the past 60 days
        # -----------------------------------------------------------------------
        print("Seeding 20 error logs...")
        admin_user = seeded_users[0]
        seller_user = seeded_sellers[0] if seeded_sellers else seeded_users[-1]

        error_log_dicts = []
        for idx, tmpl in enumerate(ERROR_TEMPLATES):
            days_ago = rng.randint(1, 60)
            hours_ago = rng.randint(0, 23)
            created_at = now - timedelta(days=days_ago, hours=hours_ago)
            user_id = admin_user.id if idx % 3 == 0 else (seller_user.id if idx % 3 == 1 else None)
            error_log_dicts.append({
                "message": tmpl["message"],
                "stack_trace": tmpl.get("stack_trace"),
                "exception_type": tmpl.get("exception_type"),
                "user_id": user_id,
                "path": tmpl["path"],
                "source": tmpl.get("source"),
                "created_at": created_at,
            })
        session.bulk_insert_mappings(ErrorLog, error_log_dicts)
        session.flush()

        # -----------------------------------------------------------------------
        # 120 historical invoices distributed over the past 12 months
        # -----------------------------------------------------------------------
        print("Seeding 120 historical invoices...")
        iva_12 = next((t for t in seeded_taxes if "12" in t.name), seeded_taxes[0])

        invoice_counter = 1
        invoice_dicts = []
        detail_dicts = []
        audit_stock_dicts = []

        # Distribute 120 invoices across 12 months (~10/month)
        for inv_idx in range(120):
            months_ago = inv_idx // 10  # 0..11
            extra_days = rng.randint(0, 27)
            issue_date = now - timedelta(days=months_ago * 30 + extra_days)

            seller = rng.choice(seeded_sellers) if seeded_sellers else seeded_users[-1]
            client = rng.choice(all_clients)
            client_name = f"{client.first_name} {client.last_name}".strip()
            seller_name = f"{seller.name} {seller.last_name}".strip()

            # 1-4 products per invoice
            n_items = rng.randint(1, 4)
            chosen_products = rng.sample(all_products, min(n_items, len(all_products)))

            subtotal = Decimal("0.00")
            tax_total = Decimal("0.00")
            line_data: list[dict] = []

            for prod in chosen_products:
                qty = rng.randint(1, 5)
                price = prod.price or Decimal("1.00")
                line_sub = _q(price * Decimal(qty))
                line_tax = _q(line_sub * iva_12.current_rate / Decimal("100"))
                subtotal = _q(subtotal + line_sub)
                tax_total = _q(tax_total + line_tax)
                line_data.append({
                    "product_id": prod.id,
                    "product_name": prod.name,
                    "quantity": qty,
                    "unit_price_snapshot": price,
                    "iva_id": iva_12.id,
                    "iva_rate": iva_12.current_rate,
                    "iva_amount": line_tax,
                })

            invoice_number = f"001-001-{invoice_counter:09d}"
            invoice_counter += 1

            invoice_dicts.append({
                "client_id": client.id,
                "issue_date": issue_date,
                "subtotal_snapshot": subtotal,
                "tax_total_snapshot": tax_total,
                "total_snapshot": _q(subtotal + tax_total),
                "invoice_number": invoice_number,
                "status": InvoiceStatus.CONFIRMED,
                "user_id": seller.id,
                "payment_method": PaymentMethod.CASH,
                "client_name_snapshot": client_name,
                "client_email_snapshot": client.email,
                "client_cedula_snapshot": client.cedula,
                "seller_name_snapshot": seller_name,
                "version": 0,
            })
            # Store line_data for later detail insertion
            # We'll flush invoices first, then match by invoice_number
            # Use a sentinel approach: store alongside idx
            detail_dicts.append((invoice_number, line_data, seller.id, issue_date))

        session.bulk_insert_mappings(Invoice, invoice_dicts)
        session.flush()

        # Re-fetch inserted invoices by invoice_number to get their IDs
        invoice_numbers = [d["invoice_number"] for d in invoice_dicts]
        from sqlalchemy import func as sql_func

        invoice_rows = session.execute(
            select(Invoice).where(Invoice.invoice_number.in_(invoice_numbers))
        ).scalars().all()
        inv_by_number = {inv.invoice_number: inv for inv in invoice_rows}

        print("Seeding invoice details and stock audit logs...")
        all_detail_dicts = []
        all_detail_tax_dicts = []

        for (inv_number, line_data, seller_id, issue_date) in detail_dicts:
            inv_obj = inv_by_number.get(inv_number)
            if inv_obj is None:
                continue
            for line in line_data:
                all_detail_dicts.append({
                    "invoice_id": inv_obj.id,
                    "product_id": line["product_id"],
                    "product_name": line["product_name"],
                    "quantity": line["quantity"],
                    "unit_price_snapshot": line["unit_price_snapshot"],
                })

        session.bulk_insert_mappings(InvoiceDetail, all_detail_dicts)
        session.flush()

        # Re-fetch details to get IDs for taxes
        detail_rows = session.execute(
            select(InvoiceDetail).where(
                InvoiceDetail.invoice_id.in_([inv_obj.id for inv_obj in inv_by_number.values()])
            )
        ).scalars().all()

        from app.infrastructure.db.models.invoice_detail_tax import InvoiceDetailTax
        detail_tax_dicts = []
        for d in detail_rows:
            detail_tax_dicts.append({
                "detail_id": d.id,
                "tax_id": iva_12.id,
                "rate_snapshot": iva_12.current_rate,
                "calculated_amount_snapshot": _q(
                    (d.unit_price_snapshot or Decimal("0")) * Decimal(d.quantity or 1) * iva_12.current_rate / Decimal("100")
                ),
            })
        session.bulk_insert_mappings(InvoiceDetailTax, detail_tax_dicts)
        session.flush()

        # -----------------------------------------------------------------------
        # Stock audit logs for each invoice detail (before → after)
        # -----------------------------------------------------------------------
        print("Seeding stock audit logs (before/after per product sale)...")

        # Build a running stock tracker to simulate before/after
        stock_tracker: dict[int, int] = {}
        for p in all_products:
            stock_tracker[p.id] = int(p.stock or 0)

        # Process invoices in chronological order
        chronological = sorted(detail_dicts, key=lambda x: x[3])  # sort by issue_date
        stock_audit_dicts = []

        for (inv_number, line_data, seller_id, issue_date) in chronological:
            inv_obj = inv_by_number.get(inv_number)
            if inv_obj is None:
                continue
            for line in line_data:
                pid = line["product_id"]
                qty = line["quantity"]
                prev_stock = stock_tracker.get(pid, 0)
                # We can't go negative in audit; cap at 0
                new_stock = max(0, prev_stock - qty)
                stock_tracker[pid] = new_stock

                stock_audit_dicts.append({
                    "action": "STOCK_CHANGE",
                    "entity": "Product",
                    "entity_id": pid,
                    "user_id": seller_id,
                    "detail": json.dumps(
                        {
                            "motivo": "venta",
                            "factura_id": inv_obj.id,
                            "factura_numero": inv_number,
                            "producto": line["product_name"],
                            "cantidad_vendida": qty,
                            "before": {"stock": prev_stock},
                            "after": {"stock": new_stock},
                        },
                        ensure_ascii=False,
                    ),
                    "created_at": issue_date,
                })

        session.bulk_insert_mappings(AuditLog, stock_audit_dicts)
        session.flush()

    print("\nDemo seed complete.")
    print("  - 6 users (3 admins, 3 sellers)")
    print(f"  - {len(DEMO_TAXES)} taxes")
    print(f"  - {DEMO_PRODUCT_COUNT} products")
    print(f"  - {DEMO_CLIENT_COUNT} clients")
    print("  - 20 error logs (distributed over past 60 days)")
    print("  - 120 historical invoices (CONFIRMED, distributed over 12 months)")
    print(f"  - {len(stock_audit_dicts)} stock audit log entries")
    print("\nCredentials:")
    for spec in DEMO_USERS:
        role = "ADMIN" if "admin" in spec["username"] else "SELLER"
        print(f"  [{role}] {spec['email']} / {spec['password']}")


if __name__ == "__main__":
    main()
