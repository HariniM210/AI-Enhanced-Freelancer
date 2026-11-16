"""Client project creation and public marketplace reads."""

from __future__ import annotations

from datetime import date, datetime, time, timezone
from typing import Any, Optional

from bson import ObjectId
from bson.errors import InvalidId
from pymongo import ASCENDING, DESCENDING

from Backend.database import get_database
from Backend.models.project import ProjectCreate


def _collection(name: str):
    """Resolve a collection through the single shared database connection."""
    return get_database()[name]


def _as_object_id(value: str) -> Optional[ObjectId]:
    try:
        return ObjectId(str(value))
    except (InvalidId, TypeError):
        return None


def _iso_datetime(value: Any) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.isoformat()
    return str(value)


def _iso_date(value: Any) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    return str(value)


def public_project(
    project: dict[str, Any], applications_count: int = 0
) -> dict[str, Any]:
    """Return the project shape expected by the frontend contract."""
    client_id = project.get("client_id")
    return {
        "id": str(project["_id"]),
        "title": str(project.get("title") or ""),
        "description": str(project.get("description") or ""),
        "category": str(project.get("category") or ""),
        "skills": [
            str(skill)
            for skill in (project.get("skills") or [])
            if skill is not None and str(skill).strip()
        ],
        "budget_min": project.get("budget_min"),
        "budget_max": project.get("budget_max"),
        "currency": str(project.get("currency") or "USD"),
        "budget_type": str(project.get("budget_type") or "fixed"),
        "deadline": _iso_date(project.get("deadline")),
        "duration": project.get("duration"),
        "experience_level": project.get("experience_level"),
        "status": str(project.get("status") or "open"),
        "client_id": str(client_id) if client_id is not None else None,
        "client_name": str(project.get("client_name") or ""),
        "location": str(project.get("location") or ""),
        "requirements": [
            str(requirement)
            for requirement in (project.get("requirements") or [])
        ],
        "deliverables": [
            str(deliverable)
            for deliverable in (project.get("deliverables") or [])
        ],
        "created_at": _iso_datetime(project.get("created_at")),
        "updated_at": _iso_datetime(project.get("updated_at")),
        "applications_count": int(applications_count),
    }


def create_project(
    payload: ProjectCreate, client: dict[str, Any]
) -> dict[str, Any]:
    """Insert a project owned by the authenticated client."""
    client_id = _as_object_id(client.get("id", ""))
    if client_id is None:
        raise ValueError("Invalid client id.")

    now = datetime.now(timezone.utc)
    project = {
        "_id": ObjectId(),
        "title": payload.title,
        "description": payload.description,
        "category": payload.category,
        "skills": payload.skills,
        "experience_level": payload.experience_level,
        "budget_type": payload.budget_type,
        "budget_min": payload.budget_min,
        "budget_max": payload.budget_max,
        "currency": payload.currency,
        "deadline": datetime.combine(
            payload.deadline, time.min, tzinfo=timezone.utc
        ),
        "duration": payload.duration,
        "requirements": payload.requirements or [],
        "deliverables": payload.deliverables or [],
        "location": payload.location or "",
        "status": "open",
        "client_id": client_id,
        "client_name": client.get("company_name") or client.get("name") or "",
        "created_at": now,
        "updated_at": now,
    }
    _collection("projects").insert_one(project)
    return project


def _application_counts(project_ids: list[ObjectId]) -> dict[ObjectId, int]:
    """Count active applications, excluding withdrawn records."""
    if not project_ids:
        return {}

    pipeline = [
        {
            "$match": {
                "project_id": {"$in": project_ids},
                "status": {"$ne": "withdrawn"},
            }
        },
        {"$group": {"_id": "$project_id", "count": {"$sum": 1}}},
    ]
    return {
        row["_id"]: int(row["count"])
        for row in _collection("applications").aggregate(pipeline)
    }


def list_projects(
    *,
    mine: bool,
    status: Optional[str],
    limit: int,
    sort: str,
    client_id: Optional[str] = None,
) -> tuple[list[dict[str, Any]], int]:
    """Return a page of projects plus the total before the limit."""
    query: dict[str, Any] = {}

    if mine:
        owner_id = _as_object_id(client_id or "")
        if owner_id is None:
            return [], 0
        query["client_id"] = owner_id

    if status:
        query["status"] = status
    elif not mine:
        # The public marketplace only shows open work by default. A client's
        # own list intentionally includes every status.
        query["status"] = "open"

    collection = _collection("projects")
    total = collection.count_documents(query)
    cursor = collection.find(query)

    if sort == "deadline":
        cursor = cursor.sort(
            [("deadline", ASCENDING), ("created_at", DESCENDING)]
        )
    else:
        cursor = cursor.sort([("created_at", DESCENDING)])

    projects = list(cursor.limit(limit))
    counts = _application_counts([project["_id"] for project in projects])
    items = [
        public_project(project, counts.get(project["_id"], 0))
        for project in projects
    ]
    return items, total


def get_project(project_id: str) -> Optional[dict[str, Any]]:
    """Return one project with its current application count."""
    object_id = _as_object_id(project_id)
    if object_id is None:
        return None

    project = _collection("projects").find_one({"_id": object_id})
    if project is None:
        return None

    count = _collection("applications").count_documents(
        {"project_id": object_id, "status": {"$ne": "withdrawn"}}
    )
    return public_project(project, count)
