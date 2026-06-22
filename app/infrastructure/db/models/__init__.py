"""SQLAlchemy ORM models.

Models import the declarative `Base` from `app.infrastructure.db.base` and
declare the schema 1:1 with the Prisma schema in Proyecto_A/pos-api, plus
two additions:
- `processed_events` (idempotency table for inbound broker events).
- The `invoices.status` enum gains `PENDING_VALIDATION`, `VALIDATED`, and
  `REJECTED` (legacy `CONFIRMED`/`CANCELLED` preserved).
"""

from app.infrastructure.db.models.blocked_user import BlockedUser
from app.infrastructure.db.models.client import Client
from app.infrastructure.db.models.error_log import ErrorLog
from app.infrastructure.db.models.invoice import Invoice
from app.infrastructure.db.models.invoice_detail import InvoiceDetail
from app.infrastructure.db.models.invoice_detail_tax import InvoiceDetailTax
from app.infrastructure.db.models.processed_event import ProcessedEvent
from app.infrastructure.db.models.product import Product
from app.infrastructure.db.models.product_tax import ProductTax
from app.infrastructure.db.models.role import Role
from app.infrastructure.db.models.stock_movement import StockMovement
from app.infrastructure.db.models.tax import Tax
from app.infrastructure.db.models.user import User
from app.infrastructure.db.models.user_role import UserRole

__all__ = [
    "BlockedUser",
    "Client",
    "ErrorLog",
    "Invoice",
    "InvoiceDetail",
    "InvoiceDetailTax",
    "ProcessedEvent",
    "Product",
    "ProductTax",
    "Role",
    "StockMovement",
    "Tax",
    "User",
    "UserRole",
]
