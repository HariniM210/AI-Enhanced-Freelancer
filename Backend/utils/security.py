"""Password hashing and JWT helpers.

Passwords are hashed with bcrypt. Tokens are signed with PyJWT using HS256.
The signing secret is read from JWT_SECRET in the root .env and is never
logged or returned in an API response.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

import bcrypt
import jwt

from Backend.config import get_settings

JWT_ALGORITHM = "HS256"
MAX_PASSWORD_BYTES = 72


class TokenError(Exception):
    """Raised when a JWT is missing, malformed, expired, or has the wrong type."""


def hash_password(password: str) -> str:
    """Return a bcrypt hash suitable for storage."""
    encoded = password.encode("utf-8")
    if len(encoded) > MAX_PASSWORD_BYTES:
        raise ValueError("Password is too long for bcrypt.")
    return bcrypt.hashpw(encoded, bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    """Constant-time bcrypt check that never raises on bad input."""
    if not password or not password_hash:
        return False
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except (ValueError, TypeError):
        return False


def normalize_email(email: str) -> str:
    """Trim and lowercase so uniqueness is case-insensitive."""
    return (email or "").strip().lower()


def _jwt_secret() -> str:
    secret = get_settings().jwt_secret
    if not secret:
        raise RuntimeError(
            "JWT_SECRET is not configured. Add a long random value to the root .env file."
        )
    return secret


def create_access_token(user_id: str, email: str, role: str) -> str:
    """Create a signed access token with user id, email, and role claims."""
    settings = get_settings()
    now = datetime.now(timezone.utc)
    payload: dict[str, Any] = {
        "sub": str(user_id),
        "email": normalize_email(email),
        "role": role,
        "type": "access",
        "iat": now,
        "exp": now + timedelta(minutes=settings.jwt_expire_minutes),
    }
    return jwt.encode(payload, _jwt_secret(), algorithm=JWT_ALGORITHM)


def decode_access_token(token: str) -> dict[str, Any]:
    """Verify signature + expiry and return the claims.

    Raises TokenError for anything the caller should treat as a 401.
    """
    try:
        payload = jwt.decode(
            token,
            _jwt_secret(),
            algorithms=[JWT_ALGORITHM],
            options={"require": ["exp", "iat", "sub"]},
        )
    except jwt.ExpiredSignatureError as exc:
        raise TokenError("Token has expired.") from exc
    except jwt.InvalidTokenError as exc:
        raise TokenError("Invalid token.") from exc

    if payload.get("type") != "access":
        raise TokenError("Invalid token type.")
    if payload.get("role") not in {"freelancer", "client"}:
        raise TokenError("Invalid token role.")
    return payload
