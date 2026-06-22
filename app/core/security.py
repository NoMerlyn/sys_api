"""Security primitives: password hashing and JWT encode/decode.

Implementation lives here; the actual issue/verify of tokens is wired up in
L3 (auth application layer + auth router). Keeping the primitives in one
place so the validator service can re-use them with the same secret.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from jose import JWTError, jwt
from passlib.context import CryptContext

# Reusable bcrypt context (cost 12 is the sweet spot for dev + small prod).
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(plain: str) -> str:
    return pwd_context.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def create_access_token(
    *,
    subject: str,
    secret: str,
    issuer: str,
    audience: str,
    algorithm: str,
    ttl_seconds: int,
    extra_claims: dict[str, Any] | None = None,
) -> tuple[str, int]:
    """Encode a JWT. Returns (token, expires_in_seconds)."""
    now = datetime.now(tz=UTC)
    exp = now + timedelta(seconds=ttl_seconds)
    payload: dict[str, Any] = {
        "sub": subject,
        "iat": int(now.timestamp()),
        "exp": int(exp.timestamp()),
        "iss": issuer,
        "aud": audience,
    }
    if extra_claims:
        payload.update(extra_claims)
    token = jwt.encode(payload, secret, algorithm=algorithm)
    return token, ttl_seconds


def decode_access_token(
    token: str, *, secret: str, issuer: str, audience: str, algorithm: str
) -> dict[str, Any]:
    """Decode and validate a JWT. Raises `jose.JWTError` on any failure."""
    return jwt.decode(
        token,
        secret,
        algorithms=[algorithm],
        issuer=issuer,
        audience=audience,
    )


__all__ = [
    "JWTError",
    "create_access_token",
    "decode_access_token",
    "hash_password",
    "verify_password",
]
