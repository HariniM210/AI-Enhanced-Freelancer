"""Authentication business logic backed by MongoDB.

This module owns user/profile document shapes. Routes stay thin: they only
translate service results into HTTP status codes.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from bson import ObjectId
from bson.errors import InvalidId
from pymongo.errors import DuplicateKeyError

from Backend.database import get_database
from Backend.models.user import RegisterRequest
from Backend.utils.security import hash_password, normalize_email, verify_password


class EmailAlreadyExistsError(Exception):
    """Raised when registration uses an email that is already registered."""


def _collection(name: str):
    """Resolve a collection through the single shared database connection."""
    return get_database()[name]


def experience_level_for_years(years: int) -> str:
    """Default experience level from years of experience."""
    if years < 2:
        return "Entry"
    if years < 5:
        return "Intermediate"
    return "Expert"


def public_user(user: dict[str, Any]) -> dict[str, Any]:
    """Return only fields safe to expose to the client (never the hash)."""
    return {
        "id": str(user["_id"]),
        "name": user.get("name", ""),
        "email": user.get("email", ""),
        "role": user.get("role", "freelancer"),
        "company_name": user.get("company_name"),
        "headline": user.get("headline"),
        "years_experience": user.get("years_experience"),
    }


def find_user_by_email(email: str) -> Optional[dict[str, Any]]:
    return _collection("users").find_one({"email": normalize_email(email)})


def find_user_by_id(user_id: str) -> Optional[dict[str, Any]]:
    try:
        object_id = ObjectId(str(user_id))
    except (InvalidId, TypeError):
        return None
    return _collection("users").find_one({"_id": object_id})


def create_user(payload: RegisterRequest) -> dict[str, Any]:
    """Insert a user plus the matching profile document.

    The user and profile share the same ``_id`` so the frontend's ``user.id``
    is directly usable with ``GET /freelancers/{id}``.
    """
    now = datetime.now(timezone.utc)
    email = normalize_email(payload.email)
    user_id = ObjectId()
    users = _collection("users")

    # Friendly pre-check; the unique index still protects against races.
    if users.find_one({"email": email}) is not None:
        raise EmailAlreadyExistsError("An account with this email already exists.")

    user_doc: dict[str, Any] = {
        "_id": user_id,
        "name": payload.name,
        "email": email,
        "password_hash": hash_password(payload.password),
        "role": payload.role,
        "is_active": True,
        "created_at": now,
        "updated_at": now,
    }
    if payload.role == "freelancer":
        user_doc["headline"] = payload.headline
        user_doc["years_experience"] = payload.years_experience
    else:
        user_doc["company_name"] = payload.company_name

    try:
        users.insert_one(user_doc)
    except DuplicateKeyError as exc:
        # Handles the race between the pre-check and the insert.
        raise EmailAlreadyExistsError(
            "An account with this email already exists."
        ) from exc

    profile: dict[str, Any] = {
        "_id": user_id,
        "user_id": user_id,
        "name": payload.name,
        "email": email,
        "created_at": now,
        "updated_at": now,
    }

    if payload.role == "freelancer":
        profile.update(
            {
                "headline": payload.headline,
                "summary": "",
                "location": "",
                "availability": "Available now",
                "skills": [],
                "years_experience": payload.years_experience,
                "experience_level": experience_level_for_years(payload.years_experience or 0),
                "hourly_rate": None,
                "currency": "USD",
                "avg_rating": 0.0,
                "reviews_count": 0,
                "completed_projects": 0,
                "avatar_url": None,
                "portfolio": [],
                "work_history": [],
            }
        )
        profile_collection = "freelancers"
    else:
        profile.update(
            {
                "company_name": payload.company_name,
                "location": "",
                "avatar_url": None,
            }
        )
        profile_collection = "clients"

    try:
        _collection(profile_collection).insert_one(profile)
    except Exception:
        # Do not leave a user account without its profile.
        users.delete_one({"_id": user_id})
        raise

    return user_doc


def authenticate_user(email: str, password: str) -> Optional[dict[str, Any]]:
    """Return the user document only when the credentials are valid."""
    user = find_user_by_email(email)
    if user is None:
        return None
    if not user.get("is_active", True):
        return None
    if not verify_password(password, user.get("password_hash", "")):
        return None
    return user
