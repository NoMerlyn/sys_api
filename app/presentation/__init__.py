"""Presentation layer: FastAPI routers and dependencies.

Routers in this package must NOT contain business logic. They:
  1. Parse and validate inputs (Pydantic DTOs).
  2. Resolve the request-scoped session and repositories via `app.presentation.deps`.
  3. Invoke a single application handler (command or query).
  4. Translate the result into the response DTO and return.
"""
