"""Sales report use cases.

Reads from the database via the same Unit-of-Work seam as the
write side, returning aggregated dictionaries ready for the
admin ReportsView.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.db.models.invoice import Invoice, InvoiceStatus
from app.infrastructure.db.models.invoice_detail import InvoiceDetail
from app.infrastructure.db.models.user import User


@dataclass(frozen=True, slots=True)
class SalesSummaryQuery:
    since: datetime | None = None
    until: datetime | None = None


class SalesSummaryHandler:
    """Aggregate stats for the top of the ReportsView."""

    async def handle(
        self, q: SalesSummaryQuery, session: AsyncSession
    ) -> dict[str, object]:
        where_clauses = [Invoice.status == InvoiceStatus.CONFIRMED]
        if q.since is not None:
            where_clauses.append(Invoice.issue_date >= q.since)
        if q.until is not None:
            where_clauses.append(Invoice.issue_date <= q.until)

        # Totals
        totals_stmt = select(
            func.count(Invoice.id),
            func.coalesce(func.sum(Invoice.total_snapshot), 0),
            func.coalesce(func.avg(Invoice.total_snapshot), 0),
            func.count(func.distinct(Invoice.client_id)),
            func.count(func.distinct(Invoice.user_id)),
        ).where(*where_clauses)
        total_invoices, total_amount, avg_amount, distinct_clients, distinct_sellers = (
            await session.execute(totals_stmt)
        ).one()

        # By status (kept compact: just count per status)
        by_status_stmt = select(
            Invoice.status, func.count(Invoice.id)
        ).group_by(Invoice.status)
        by_status = {
            str(r[0]): r[1] for r in (await session.execute(by_status_stmt)).all()
        }

        return {
            "total_invoices": int(total_invoices),
            "total_amount": float(total_amount),
            "avg_amount": float(avg_amount),
            "distinct_clients": int(distinct_clients),
            "distinct_sellers": int(distinct_sellers),
            "by_status": by_status,
        }


@dataclass(frozen=True, slots=True)
class TopProductsQuery:
    limit: int = 10
    since: datetime | None = None
    until: datetime | None = None


class TopProductsHandler:
    """Top-N products by total revenue in confirmed invoices."""

    async def handle(
        self, q: TopProductsQuery, session: AsyncSession
    ) -> list[dict[str, object]]:
        stmt = (
            select(
                InvoiceDetail.product_id,
                InvoiceDetail.product_name,
                func.sum(InvoiceDetail.quantity).label("qty"),
                func.sum(InvoiceDetail.unit_price_snapshot * InvoiceDetail.quantity).label("revenue"),
                func.count(func.distinct(InvoiceDetail.invoice_id)).label("invoices"),
            )
            .join(Invoice, Invoice.id == InvoiceDetail.invoice_id)
            .where(Invoice.status == InvoiceStatus.CONFIRMED)
            .group_by(InvoiceDetail.product_id, InvoiceDetail.product_name)
            .order_by(func.sum(InvoiceDetail.unit_price_snapshot * InvoiceDetail.quantity).desc())
            .limit(q.limit)
        )
        if q.since is not None:
            stmt = stmt.where(Invoice.issue_date >= q.since)
        if q.until is not None:
            stmt = stmt.where(Invoice.issue_date <= q.until)

        rows = (await session.execute(stmt)).all()
        return [
            {
                "product_id": r.product_id,
                "product_name": r.product_name,
                "quantity": float(r.qty or 0),
                "revenue": float(r.revenue or 0),
                "invoices": int(r.invoices or 0),
            }
            for r in rows
        ]


@dataclass(frozen=True, slots=True)
class TopClientsQuery:
    limit: int = 10
    since: datetime | None = None
    until: datetime | None = None


class TopClientsHandler:
    """Top-N clients by total spent in confirmed invoices."""

    async def handle(
        self, q: TopClientsQuery, session: AsyncSession
    ) -> list[dict[str, object]]:
        stmt = (
            select(
                Invoice.client_id,
                func.coalesce(Invoice.client_name_snapshot, "Consumidor final").label(
                    "client_name"
                ),
                func.count(Invoice.id).label("invoices"),
                func.coalesce(func.sum(Invoice.total_snapshot), 0).label("spent"),
            )
            .where(Invoice.status == InvoiceStatus.CONFIRMED)
            .group_by(Invoice.client_id, Invoice.client_name_snapshot)
            .order_by(func.sum(Invoice.total_snapshot).desc())
            .limit(q.limit)
        )
        if q.since is not None:
            stmt = stmt.where(Invoice.issue_date >= q.since)
        if q.until is not None:
            stmt = stmt.where(Invoice.issue_date <= q.until)

        rows = (await session.execute(stmt)).all()
        return [
            {
                "client_id": r.client_id,
                "client_name": r.client_name,
                "invoices": int(r.invoices),
                "spent": float(r.spent),
            }
            for r in rows
        ]


@dataclass(frozen=True, slots=True)
class SalesByDayQuery:
    since: datetime | None = None
    until: datetime | None = None


class SalesByDayHandler:
    """Daily revenue for the requested window (for line/bar charts)."""

    async def handle(
        self, q: SalesByDayQuery, session: AsyncSession
    ) -> list[dict[str, object]]:
        day_col = func.date(Invoice.issue_date).label("day")
        stmt = (
            select(
                day_col,
                func.count(Invoice.id).label("invoices"),
                func.coalesce(func.sum(Invoice.total_snapshot), 0).label("revenue"),
            )
            .where(Invoice.status == InvoiceStatus.CONFIRMED)
            .group_by(day_col)
            .order_by(day_col)
        )
        if q.since is not None:
            stmt = stmt.where(Invoice.issue_date >= q.since)
        if q.until is not None:
            stmt = stmt.where(Invoice.issue_date <= q.until)

        rows = (await session.execute(stmt)).all()
        return [
            {
                "day": r.day.isoformat() if isinstance(r.day, (date, datetime)) else str(r.day),
                "invoices": int(r.invoices),
                "revenue": float(r.revenue),
            }
            for r in rows
        ]


@dataclass(frozen=True, slots=True)
class TopSellersQuery:
    limit: int = 10
    since: datetime | None = None
    until: datetime | None = None


class TopSellersHandler:
    """Top-N sellers by total sales."""

    async def handle(
        self, q: TopSellersQuery, session: AsyncSession
    ) -> list[dict[str, object]]:
        stmt = (
            select(
                User.id,
                User.username,
                User.name,
                User.last_name,
                func.count(Invoice.id).label("invoices"),
                func.coalesce(func.sum(Invoice.total_snapshot), 0).label("sold"),
            )
            .join(Invoice, Invoice.user_id == User.id)
            .where(Invoice.status == InvoiceStatus.CONFIRMED)
            .group_by(User.id, User.username, User.name, User.last_name)
            .order_by(func.sum(Invoice.total_snapshot).desc())
            .limit(q.limit)
        )
        if q.since is not None:
            stmt = stmt.where(Invoice.issue_date >= q.since)
        if q.until is not None:
            stmt = stmt.where(Invoice.issue_date <= q.until)

        rows = (await session.execute(stmt)).all()
        return [
            {
                "user_id": r.id,
                "username": r.username,
                "name": r.name,
                "last_name": r.last_name,
                "invoices": int(r.invoices),
                "sold": float(r.sold),
            }
            for r in rows
        ]
