"""FastAPI application factory and lifespan management."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from app.config import get_settings
from app.core.exceptions import (
    AppError,
    BusinessError,
    app_error_handler,
    business_exception_handler,
)
from app.core.rate_limit import limiter
from app.infrastructure.db.session import dispose_engine, init_engine
from app.infrastructure.messaging.rabbit import (
    declare_topology,
    get_channel_pool,
    shutdown_channel_pool,
)

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    import asyncio

    from app.infrastructure.messaging.consumer import run_invoice_consumer

    settings = get_settings()
    logger.info("Starting sys_api (env=%s)", settings.env)

    init_engine(settings.database_url)
    await get_channel_pool(settings.rabbitmq_url)
    await declare_topology()

    consumer_task = asyncio.create_task(
        run_invoice_consumer(settings.rabbitmq_url),
        name="invoice-broker-consumer",
    )
    logger.info("invoice-broker-consumer task scheduled")

    try:
        yield
    finally:
        consumer_task.cancel()
        await shutdown_channel_pool()
        await dispose_engine()
        logger.info("sys_api shutdown complete")


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title="POS API",
        description=("API de facturación con Clean Architecture. Reemplaza Proyecto_A/pos-api."),
        version="0.1.0",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.state.limiter = limiter
    app.add_middleware(SlowAPIMiddleware)

    app.add_exception_handler(AppError, app_error_handler)  # type: ignore[arg-type]
    app.add_exception_handler(BusinessError, business_exception_handler)  # type: ignore[arg-type]

    @app.exception_handler(RateLimitExceeded)
    async def _rate_limit_handler(_: Request, exc: RateLimitExceeded) -> JSONResponse:
        return JSONResponse(
            status_code=429,
            content={
                "code": "RATE_LIMIT_EXCEEDED",
                "message": f"Demasiadas solicitudes. Límite: {exc.detail}",
            },
        )

    @app.exception_handler(RequestValidationError)
    async def _validation_error_handler(_: Request, exc: RequestValidationError) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content={
                "code": "VALIDATION_ERROR",
                "message": "Request validation failed",
                "details": exc.errors(),
            },
        )

    @app.get("/health", tags=["health"])
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    # Liveness + readiness probes.
    from app.presentation.routers import health as _health_router

    app.include_router(_health_router.router)

    # Routers
    from app.presentation.routers import auth as auth_router
    from app.presentation.routers import clients as clients_router
    from app.presentation.routers import products as products_router
    from app.presentation.routers import roles as roles_router
    from app.presentation.routers import taxes as taxes_router
    from app.presentation.routers import users as users_router

    app.include_router(auth_router.router, prefix="/api")
    app.include_router(users_router.router, prefix="/api")
    app.include_router(roles_router.router, prefix="/api")
    app.include_router(clients_router.router, prefix="/api")
    app.include_router(products_router.router, prefix="/api")
    app.include_router(taxes_router.router, prefix="/api")

    # Invoices router
    from app.presentation.routers import invoice_pdf as invoice_pdf_router
    from app.presentation.routers import invoices as invoices_router

    app.include_router(invoices_router.router, prefix="/api")
    app.include_router(invoice_pdf_router.router, prefix="/api")

    return app


app = create_app()
