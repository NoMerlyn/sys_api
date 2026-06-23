"""Rate limiting (slowapi) for the public auth surface.

`login_limiter` is 5 requests / minute per client IP. The lock-after-3-
failures policy in `login_command.py` is still the primary defense;
this limiter is the broader throttling that also covers
`/auth/register` if you ever expose it publicly.
"""

from __future__ import annotations

from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)


def login_rate_limit() -> str:
    """Identifier used as the slowapi `key` for the login endpoint."""
    return "login"
