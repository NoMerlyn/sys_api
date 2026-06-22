"""Stock movement type enum."""

from __future__ import annotations

import enum


class MovementType(str, enum.Enum):
    ENTRY = "ENTRY"
    EXIT = "EXIT"
