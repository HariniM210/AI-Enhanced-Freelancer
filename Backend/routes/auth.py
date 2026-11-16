"""Authentication routes: register, login, and current user.

Logout is intentionally not a server endpoint. Tokens are stateless: the
frontend deletes its stored token, but a copied token stays valid until it
expires. Real revocation would require a server-side denylist or token
version per user, which is outside Phase 2.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from Backend.dependencies import get_current_user
from Backend.models.user import AuthResponse, LoginRequest, RegisterRequest, UserPublic
from Backend.services.auth_service import (
    EmailAlreadyExistsError,
    authenticate_user,
    create_user,
    public_user,
)
from Backend.utils.security import create_access_token

router = APIRouter(prefix="/auth", tags=["auth"])


def _auth_response(user: dict) -> dict:
    token = create_access_token(user["_id"], user["email"], user["role"])
    return {
        "access_token": token,
        "token_type": "bearer",
        "user": public_user(user),
    }


@router.post(
    "/register",
    response_model=AuthResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a freelancer or client",
)
def register(payload: RegisterRequest) -> dict:
    try:
        user = create_user(payload)
    except EmailAlreadyExistsError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists.",
        ) from exc
    return _auth_response(user)


@router.post(
    "/login",
    response_model=AuthResponse,
    summary="Log in and receive a JWT access token",
)
def login(payload: LoginRequest) -> dict:
    user = authenticate_user(payload.email, payload.password)
    if user is None:
        # Same message for unknown email, wrong password, and inactive account.
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return _auth_response(user)


@router.get(
    "/me",
    response_model=UserPublic,
    summary="Return the authenticated user",
)
def me(current_user: dict = Depends(get_current_user)) -> dict:
    return current_user
