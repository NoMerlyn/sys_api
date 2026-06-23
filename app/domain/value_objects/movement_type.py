"""Stock movement type enum."""

from __future__ import annotations

import enum


class MovementType(enum.StrEnum):
    ENTRY = "ENTRY"
    EXIT = "EXIT"
