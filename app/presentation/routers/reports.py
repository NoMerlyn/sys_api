"""Admin-only sales report endpoints."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response

from app.application.common.uow import uow
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
from app.presentation.deps import require_role

router = APIRouter(prefix="/reports", tags=["reports"])


@router.get("/summary")
async def summary(
    _admin: Annotated[object, Depends(require_role("ADMINISTRATOR"))],
    since: datetime | None = None,
    until: datetime | None = None,
) -> dict[str, object]:
    handler = SalesSummaryHandler()
    async with uow() as session:
        return await handler.handle(SalesSummaryQuery(since=since, until=until), session)


@router.get("/top-products")
async def top_products(
    _admin: Annotated[object, Depends(require_role("ADMINISTRATOR"))],
    limit: int = Query(10, ge=1, le=100),
    since: datetime | None = None,
    until: datetime | None = None,
) -> list[dict[str, object]]:
    handler = TopProductsHandler()
    async with uow() as session:
        return await handler.handle(
            TopProductsQuery(limit=limit, since=since, until=until), session
        )


@router.get("/top-clients")
async def top_clients(
    _admin: Annotated[object, Depends(require_role("ADMINISTRATOR"))],
    limit: int = Query(10, ge=1, le=100),
    since: datetime | None = None,
    until: datetime | None = None,
) -> list[dict[str, object]]:
    handler = TopClientsHandler()
    async with uow() as session:
        return await handler.handle(TopClientsQuery(limit=limit, since=since, until=until), session)


@router.get("/top-sellers")
async def top_sellers(
    _admin: Annotated[object, Depends(require_role("ADMINISTRATOR"))],
    limit: int = Query(10, ge=1, le=100),
    since: datetime | None = None,
    until: datetime | None = None,
) -> list[dict[str, object]]:
    handler = TopSellersHandler()
    async with uow() as session:
        return await handler.handle(TopSellersQuery(limit=limit, since=since, until=until), session)


@router.get("/by-day")
async def by_day(
    _admin: Annotated[object, Depends(require_role("ADMINISTRATOR"))],
    since: datetime | None = None,
    until: datetime | None = None,
) -> list[dict[str, object]]:
    handler = SalesByDayHandler()
    async with uow() as session:
        return await handler.handle(SalesByDayQuery(since=since, until=until), session)



@router.get("/sales.xlsx")
async def sales_xlsx(
    _admin: Annotated[object, Depends(require_role("ADMINISTRATOR"))],
    limit: int = Query(100, ge=1, le=500),
    since: datetime | None = None,
    until: datetime | None = None,
) -> Response:
    from fastapi.responses import Response

    from app.application.reports.excel import build_workbook
    # Hit the existing handlers to reuse the SQL logic.
    async with uow() as session:
        summary = await SalesSummaryHandler().handle(
            SalesSummaryQuery(since=since, until=until), session
        )
        products = await TopProductsHandler().handle(
            TopProductsQuery(limit=limit, since=since, until=until), session
        )
        clients = await TopClientsHandler().handle(
            TopClientsQuery(limit=limit, since=since, until=until), session
        )
        sellers = await TopSellersHandler().handle(
            TopSellersQuery(limit=limit, since=since, until=until), session
        )
        days = await SalesByDayHandler().handle(
            SalesByDayQuery(since=since, until=until), session
        )
    blob = build_workbook(
        summary=summary,
        top_products=products,
        top_clients=clients,
        top_sellers=sellers,
        by_day=days,
    )
    return Response(
        content=blob,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": "attachment; filename=\"sales-report.xlsx\""
        },
    )
