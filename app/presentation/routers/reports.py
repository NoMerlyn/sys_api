"""Admin-only sales report endpoints."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query

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
        return await handler.handle(
            SalesSummaryQuery(since=since, until=until), session
        )


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
        return await handler.handle(
            TopClientsQuery(limit=limit, since=since, until=until), session
        )


@router.get("/top-sellers")
async def top_sellers(
    _admin: Annotated[object, Depends(require_role("ADMINISTRATOR"))],
    limit: int = Query(10, ge=1, le=100),
    since: datetime | None = None,
    until: datetime | None = None,
) -> list[dict[str, object]]:
    handler = TopSellersHandler()
    async with uow() as session:
        return await handler.handle(
            TopSellersQuery(limit=limit, since=since, until=until), session
        )


@router.get("/by-day")
async def by_day(
    _admin: Annotated[object, Depends(require_role("ADMINISTRATOR"))],
    since: datetime | None = None,
    until: datetime | None = None,
) -> list[dict[str, object]]:
    handler = SalesByDayHandler()
    async with uow() as session:
        return await handler.handle(
            SalesByDayQuery(since=since, until=until), session
        )
