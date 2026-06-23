"""Domain exceptions re-exported for convenience.

The implementations live in `app.core.exceptions` to keep the dependency
graph flat (core has no upward dependency on domain).
"""

from app.core.exceptions import BusinessError, NotFoundError

__all__ = ["BusinessError", "NotFoundError"]
