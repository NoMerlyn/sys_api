"""Domain layer: pure entities, value objects, and exceptions.

This package has zero infrastructure dependencies. The application layer
imports from here; the infrastructure layer adapts to interfaces defined
in `app.application.common.interfaces`.
"""

from app.core.exceptions import BusinessError, NotFoundError

__all__ = ["BusinessError", "NotFoundError"]
