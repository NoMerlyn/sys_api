"""Health check endpoints.

Two probes, both unauthenticated:

- GET /health/live  — process is alive; always returns 200 unless
  Python itself is broken. Use this for liveness probes (Kubernetes
  `livenessProbe` or equivalent).
- GET /health/ready — every external dependency (DB, broker) is
  reachable. Use this for readiness probes; returning 503 from this
  endpoint tells the orchestrator to stop sending traffic to this
  instance while it recovers.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Response, status
from sqlalchemy import text

from app.application.common.uow import uow

logger = logging.getLogger(__name__)

router = APIRouter(tags=["health"])


@router.get("/health/live")
async def live() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/health/ready")
async def ready(response: Response) -> dict[str, object]:
    checks: dict[str, str] = {}

    # Database
    try:
        async with uow() as session:
            await session.execute(text("SELECT 1"))
        checks["database"] = "ok"
    except Exception as exc:  # noqa: BLE001
        logger.warning("Health check: database failed: %s", exc)
        checks["database"] = f"error: {exc.__class__.__name__}"

    # Broker (RabbitMQ) — best-effort; we just want to know the
    # consumer's connection is still open. 'uninitialised' is reported
    # when the lifespan has not yet created the connection (which we
    # treat as healthy in tests; in production the lifespan should
    # have created it before the first request).
    try:
        from app.infrastructure.messaging import rabbit as _rabbit

        if _rabbit._connection is None:
            checks["broker"] = "uninitialised"
        elif _rabbit._connection.is_closed:
            checks["broker"] = "disconnected"
        else:
            checks["broker"] = "ok"
    except Exception as exc:  # noqa: BLE001
        logger.warning("Health check: broker failed: %s", exc)
        checks["broker"] = f"error: {exc.__class__.__name__}"

    overall_ok = all(v in ("ok", "uninitialised") for v in checks.values())
    if not overall_ok:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return {"status": "ok" if overall_ok else "degraded", "checks": checks}
