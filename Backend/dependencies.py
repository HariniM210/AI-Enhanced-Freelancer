"""Reusable FastAPI authentication and authorization dependencies.

Later phases import these directly, for example:

    @router.post("/projects")
    def create_project(user: dict = Depends(require_role("client"))):
        ...
"""

from __future__ import annotations

from typing import Callable

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from Backend.services.auth_service import find_user_by_id, public_user
from Backend.utils.security import TokenError, decode_access_token

# auto_error=False lets us return a consistent 401 instead of FastAPI's 403.
bearer_scheme = HTTPBearer(auto_error=False)


def _authenticated_user(credentials: HTTPAuthorizationCredentials) -> dict:
    """Validate a non-empty bearer token and return its active user."""
    try:
        payload = decode_access_token(credentials.credentials)
    except TokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token.",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    user = find_user_by_id(payload.get("sub", ""))
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not user.get("is_active", True):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This account is inactive.",
        )
    return public_user(user)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> dict:
    """Require a bearer token and return the matching active user."""
    if credentials is None or not credentials.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return _authenticated_user(credentials)


def get_optional_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> dict | None:
    """Return the user when a token is supplied, otherwise ``None``.

    Public endpoints use this so anonymous visitors can browse, while an
    invalid or expired token is still rejected instead of being ignored.
    """
    if credentials is None or not credentials.credentials:
        return None
    return _authenticated_user(credentials)


def require_role(*roles: str) -> Callable[..., dict]:
    """Build a dependency that allows only the given roles."""
    allowed = set(roles)

    def dependency(user: dict = Depends(get_current_user)) -> dict:
        if user.get("role") not in allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to perform this action.",
            )
        return user

    return dependency
