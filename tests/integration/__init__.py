"""HTTP integration tests using TestClient + a real PostgreSQL via testcontainers.

These tests verify the FastAPI HTTP layer end-to-end (validation, auth,
serialization, DB roundtrip) without subprocesses. RabbitMQ is not
included here because that would require a second consumer process; the
invoice flow ends at the publish step (PENDING_VALIDATION).
"""
