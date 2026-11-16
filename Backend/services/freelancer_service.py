"""Freelancer profile read and update logic.

Routes stay thin. This module owns the public profile shape, the fallback
profile created for older accounts, filtering/searching, and the partial
update rules.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any, Optional

from bson import ObjectId
from bson.errors import InvalidId
from pymongo import DESCENDING, ReturnDocument
from pymongo.errors import DuplicateKeyError

from Backend.database import get_database
from Backend.models.freelancer import FreelancerProfileUpdate
from Backend.services.auth_service import experience_level_for_years


def _collection(name: str):
    """Resolve a collection through the single shared database connection."""
    return get_database()[name]


def _as_object_id(value: str) -> Optional[ObjectId]:
    try:
        return ObjectId(str(value))
    except (InvalidId, TypeError):
        return None


def public_freelancer(profile: dict[str, Any]) -> dict[str, Any]:
    """Return only the public profile fields (never email or auth data)."""
    years = profile.get("years_experience")
    if years is not None:
        years = int(years)

    experience_level = (
        profile.get("experience_level") or experience_level_for_years(years or 0)
    )

    hourly_rate = profile.get("hourly_rate")
    if hourly_rate is not None:
        hourly_rate = float(hourly_rate)

    portfolio: list[dict[str, Any]] = []
    for item in profile.get("portfolio") or []:
        if not isinstance(item, dict):
            continue
        url = item.get("url")
        portfolio.append(
            {
                "title": str(item.get("title") or ""),
                "description": str(item.get("description") or ""),
                "url": str(url) if url else None,
                "technologies": [
                    str(technology)
                    for technology in (item.get("technologies") or [])
                    if technology is not None and str(technology).strip()
                ],
            }
        )

    work_history: list[dict[str, Any]] = []
    for item in profile.get("work_history") or []:
        if not isinstance(item, dict):
            continue
        work_history.append(
            {
                "role": str(item.get("role") or ""),
                "company": str(item.get("company") or ""),
                "period": str(item.get("period") or ""),
                "description": str(item.get("description") or ""),
            }
        )

    return {
        "id": str(profile["_id"]),
        "name": str(profile.get("name") or ""),
        "headline": str(profile.get("headline") or ""),
        "summary": str(profile.get("summary") or ""),
        "location": str(profile.get("location") or ""),
        "availability": str(profile.get("availability") or "Available now"),
        "skills": [
            str(skill)
            for skill in (profile.get("skills") or [])
            if skill is not None and str(skill).strip()
        ],
        "years_experience": years,
        "experience_level": experience_level,
        "hourly_rate": hourly_rate,
        "currency": str(profile.get("currency") or "USD"),
        "avg_rating": float(profile.get("avg_rating") or 0.0),
        "reviews_count": int(profile.get("reviews_count") or 0),
        "completed_projects": int(profile.get("completed_projects") or 0),
        "avatar_url": profile.get("avatar_url") or None,
        "portfolio": portfolio,
        "work_history": work_history,
    }


def _default_profile_from_user(user: dict[str, Any]) -> dict[str, Any]:
    """Build a minimal profile for a freelancer account created before Phase 3."""
    now = datetime.now(timezone.utc)
    years = user.get("years_experience")
    return {
        "_id": user["_id"],
        "user_id": user["_id"],
        "name": user.get("name") or "",
        "email": user.get("email") or "",
        "headline": user.get("headline") or "",
        "summary": "",
        "location": "",
        "availability": "Available now",
        "skills": [],
        "years_experience": years,
        "experience_level": experience_level_for_years(years or 0),
        "hourly_rate": None,
        "currency": "USD",
        "avg_rating": 0.0,
        "reviews_count": 0,
        "completed_projects": 0,
        "avatar_url": None,
        "portfolio": [],
        "work_history": [],
        "created_at": now,
        "updated_at": now,
    }


def get_freelancer_profile(
    profile_id: str, *, create_if_missing: bool = False
) -> Optional[dict[str, Any]]:
    """Find a freelancer profile, optionally healing a missing one.

    ``create_if_missing`` only creates a profile when the id belongs to an
    actual freelancer user. A client id or an unknown id still returns None.
    """
    object_id = _as_object_id(profile_id)
    if object_id is None:
        return None

    profiles = _collection("freelancers")
    profile = profiles.find_one({"_id": object_id})
    if profile is not None or not create_if_missing:
        return profile

    user = _collection("users").find_one(
        {"_id": object_id, "role": "freelancer"}
    )
    if user is None:
        return None

    profile = _default_profile_from_user(user)
    try:
        profiles.insert_one(profile)
    except DuplicateKeyError:
        # Another request created it between our find and insert.
        profile = profiles.find_one({"_id": object_id})
    return profile


def list_freelancers(
    *,
    limit: int,
    sort: Optional[str] = None,
    skills: Optional[list[str]] = None,
    q: Optional[str] = None,
) -> tuple[list[dict[str, Any]], int]:
    """Return public profiles plus the total before the limit is applied."""
    clauses: list[dict[str, Any]] = []

    if skills:
        # Match any requested skill, case-insensitively, without letting user
        # input become a regex.
        clauses.append(
            {
                "$or": [
                    {
                        "skills": {
                            "$regex": f"^{re.escape(skill)}$",
                            "$options": "i",
                        }
                    }
                    for skill in skills
                ]
            }
        )

    if q:
        pattern = {"$regex": re.escape(q), "$options": "i"}
        clauses.append(
            {
                "$or": [
                    {"name": pattern},
                    {"headline": pattern},
                    {"summary": pattern},
                    {"skills": pattern},
                ]
            }
        )

    query: dict[str, Any] = {"$and": clauses} if clauses else {}

    collection = _collection("freelancers")
    total = collection.count_documents(query)
    cursor = collection.find(query)

    if sort == "rating":
        cursor = cursor.sort(
            [("avg_rating", DESCENDING), ("reviews_count", DESCENDING)]
        )
    else:
        cursor = cursor.sort([("created_at", DESCENDING)])

    items = [public_freelancer(profile) for profile in cursor.limit(limit)]
    return items, total


def _merge_portfolio(
    existing: list[Any], incoming: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Preserve technologies when the edit form did not send that field."""
    existing_by_title: dict[str, dict[str, Any]] = {}
    for item in existing:
        if not isinstance(item, dict):
            continue
        title = str(item.get("title") or "").strip().casefold()
        if title:
            existing_by_title[title] = item

    merged: list[dict[str, Any]] = []
    for item in incoming:
        item = dict(item)
        if "technologies" not in item:
            title = str(item.get("title") or "").strip().casefold()
            old = existing_by_title.get(title)
            item["technologies"] = list(old.get("technologies") or []) if old else []
        merged.append(item)
    return merged


def _merge_work_history(
    existing: list[Any], incoming: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Preserve descriptions when the edit form did not send that field."""

    def key(item: dict[str, Any]) -> tuple[str, str, str]:
        return (
            str(item.get("role") or "").strip().casefold(),
            str(item.get("company") or "").strip().casefold(),
            str(item.get("period") or "").strip().casefold(),
        )

    existing_by_key: dict[tuple[str, str, str], dict[str, Any]] = {}
    for item in existing:
        if isinstance(item, dict):
            existing_by_key[key(item)] = item

    merged: list[dict[str, Any]] = []
    for item in incoming:
        item = dict(item)
        if "description" not in item:
            old = existing_by_key.get(key(item))
            item["description"] = str(old.get("description") or "") if old else ""
        merged.append(item)
    return merged


def update_freelancer_profile(
    user_id: str, payload: FreelancerProfileUpdate
) -> Optional[dict[str, Any]]:
    """Apply a partial update and keep the matching user document in sync."""
    profile = get_freelancer_profile(user_id, create_if_missing=True)
    if profile is None:
        return None

    updates = payload.model_dump(exclude_unset=True)

    if "skills" in updates and updates["skills"] is None:
        updates["skills"] = []

    if "portfolio" in updates:
        if updates["portfolio"] is None:
            updates["portfolio"] = []
        else:
            updates["portfolio"] = _merge_portfolio(
                profile.get("portfolio") or [], updates["portfolio"]
            )

    if "work_history" in updates:
        if updates["work_history"] is None:
            updates["work_history"] = []
        else:
            updates["work_history"] = _merge_work_history(
                profile.get("work_history") or [], updates["work_history"]
            )

    if "years_experience" in updates and "experience_level" not in updates:
        updates["experience_level"] = experience_level_for_years(
            updates["years_experience"] or 0
        )

    updates["updated_at"] = datetime.now(timezone.utc)

    updated = _collection("freelancers").find_one_and_update(
        {"_id": profile["_id"]},
        {"$set": updates},
        return_document=ReturnDocument.AFTER,
    )
    if updated is None:
        return None

    # The login response reads these fields from the users collection.
    user_updates = {
        key: updates[key]
        for key in ("name", "headline", "years_experience")
        if key in updates
    }
    if user_updates:
        user_updates["updated_at"] = updates["updated_at"]
        _collection("users").update_one(
            {"_id": profile["_id"]}, {"$set": user_updates}
        )

    return updated
