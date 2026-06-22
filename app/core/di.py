"""Dependency-injection tokens and helpers.

Repositories and the UoW are injected via `app.core.di.TOKENS` constants
in `application/common/tokens.py` (created in L4). This module exposes
generic FastAPI dependencies: settings, engine, UoW, request id.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends

from app.config import Settings, get_settings

SettingsDep = Annotated[Settings, Depends(get_settings)]


def __getattr__(name: str):  # pragma: no cover - placeholder
    if name == "TOKENS":
        # Re-exported lazily to avoid a circular import at module load time.
        from app.application.common.tokens import TOKENS  # noqa: PLC0415

        return TOKENS
    raise AttributeError(name)
