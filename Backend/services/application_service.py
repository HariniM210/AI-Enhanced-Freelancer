"""Freelancer application submission and client hiring workflow.

Phase 4 deliberately keeps the workflow small:

* a freelancer may apply once to an open project;
* the freelancer identity and the initial status always come from the server;
* a client may shortlist, reject, or hire an application;
* hiring closes the project to further hires and auto-rejects the remaining
  pending and shortlisted applications so the marketplace never shows an
  inconsistent state.

``applications_count`` is never stored. It is counted from this collection by
``project_service`` so duplicates and status changes cannot corrupt it.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any, Optional

from bson import ObjectId
from bson.errors import InvalidId
from pymongo import ASCENDING, DESCENDING, ReturnDocument
from pymongo.errors import DuplicateKeyError, OperationFailure

from Backend.database import get_database
from Backend.models.application import ApplicationCreate, ApplicationStatusUpdate
from Backend.services.freelancer_service import public_freelancer

# MongoDB returns one of these when the deployment cannot run transactions
# (for example a standalone server or the in-memory test database). In that
# case the completion workflow uses its compensating rollback instead.
TRANSACTION_UNSUPPORTED_CODES = {20, 303, 40415}


class ApplicationError(Exception):
    """Base class for application workflow errors."""


class ProjectNotFoundError(ApplicationError):
    """The project does not exist or the id is not a valid ObjectId."""


class ProjectNotOpenError(ApplicationError):
    """The project is not accepting new applications."""


class DuplicateApplicationError(ApplicationError):
    """This freelancer already applied to this project."""


class ApplicationNotFoundError(ApplicationError):
    """The application does not exist or the id is not a valid ObjectId."""


class ApplicationPermissionError(ApplicationError):
    """The authenticated user does not own the requested resource."""


class ApplicationConflictError(ApplicationError):
    """The requested transition would create an inconsistent state."""


def _collection(name: str):
    """Resolve a collection through the single shared database connection."""
    return get_database()[name]


def _as_object_id(value: Any) -> Optional[ObjectId]:
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


def _project_summary(project: Optional[dict[str, Any]]) -> Optional[dict[str, Any]]:
    """Build the nested project object used in application responses."""
    if not project:
        return None

    project_id = project.get("id", project.get("_id"))
    return {
        "id": str(project_id) if project_id is not None else "",
        "title": str(project.get("title") or ""),
        "category": str(project.get("category") or ""),
        "budget_min": project.get("budget_min"),
        "budget_max": project.get("budget_max"),
        "currency": str(project.get("currency") or "USD"),
        "budget_type": str(project.get("budget_type") or "fixed"),
        "deadline": _iso_date(project.get("deadline")),
        "status": str(project.get("status") or "open"),
        "client_name": str(project.get("client_name") or ""),
    }


def _freelancer_summary(
    profile: Optional[dict[str, Any]],
) -> Optional[dict[str, Any]]:
    """Build the public nested freelancer object.

    A database profile is passed through ``public_freelancer`` so email and
    authentication fields can never reach the response. A stored snapshot is
    already public and is used as-is.
    """
    if not profile:
        return None

    data = public_freelancer(profile) if "_id" in profile else profile
    return {
        "id": str(data.get("id") or ""),
        "name": str(data.get("name") or ""),
        "headline": str(data.get("headline") or ""),
        "summary": str(data.get("summary") or ""),
        "location": str(data.get("location") or ""),
        "availability": str(data.get("availability") or ""),
        "skills": [
            str(skill)
            for skill in (data.get("skills") or [])
            if skill is not None and str(skill).strip()
        ],
        "years_experience": data.get("years_experience"),
        "experience_level": data.get("experience_level"),
        "hourly_rate": data.get("hourly_rate"),
        "currency": str(data.get("currency") or "USD"),
        "avg_rating": float(data.get("avg_rating") or 0.0),
        "reviews_count": int(data.get("reviews_count") or 0),
        "completed_projects": int(data.get("completed_projects") or 0),
        "avatar_url": data.get("avatar_url") or None,
    }


def _stored_freelancer_snapshot(
    profile: Optional[dict[str, Any]], user: dict[str, Any]
) -> dict[str, Any]:
    summary = _freelancer_summary(profile)
    if summary is not None:
        return summary
    return {
        "id": str(user.get("id") or ""),
        "name": str(user.get("name") or ""),
        "headline": str(user.get("headline") or ""),
        "summary": "",
        "location": "",
        "availability": "Available now",
        "skills": [],
        "years_experience": user.get("years_experience"),
        "experience_level": None,
        "hourly_rate": None,
        "currency": "USD",
        "avg_rating": 0.0,
        "reviews_count": 0,
        "completed_projects": 0,
        "avatar_url": None,
    }


def public_application(
    application: dict[str, Any],
    *,
    project: Optional[dict[str, Any]] = None,
    freelancer: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    """Return the application shape expected by Frontend(2)/js/data.js.

    The nested objects are refreshed when a current document is supplied and
    otherwise come from the snapshots written at submission time.
    """
    project_summary = _project_summary(project) or _project_summary(
        application.get("project_snapshot")
    )
    freelancer_summary = _freelancer_summary(freelancer) or _freelancer_summary(
        application.get("freelancer_snapshot")
    )

    project_id = application.get("project_id")
    freelancer_id = application.get("freelancer_id")
    client_id = application.get("client_id")

    return {
        "id": str(application["_id"]),
        "project_id": str(project_id) if project_id is not None else "",
        "project_title": str(
            application.get("project_title")
            or (project_summary or {}).get("title")
            or ""
        ),
        "project_category": str(
            application.get("project_category")
            or (project_summary or {}).get("category")
            or ""
        ),
        "client_id": str(client_id) if client_id is not None else None,
        "client_name": str(
            application.get("client_name")
            or (project_summary or {}).get("client_name")
            or ""
        ),
        "freelancer_id": str(freelancer_id) if freelancer_id is not None else "",
        "freelancer_name": str(
            application.get("freelancer_name")
            or (freelancer_summary or {}).get("name")
            or ""
        ),
        "freelancer_headline": str(
            application.get("freelancer_headline")
            or (freelancer_summary or {}).get("headline")
            or ""
        ),
        "freelancer": freelancer_summary,
        "project": project_summary,
        "cover_letter": str(application.get("cover_letter") or ""),
        "bid_amount": float(application.get("bid_amount") or 0),
        "currency": str(
            application.get("currency")
            or (project_summary or {}).get("currency")
            or "USD"
        ),
        "delivery_days": application.get("delivery_days"),
        "status": str(application.get("status") or "pending"),
        "rating": application.get("rating"),
        "review": application.get("review"),
        "created_at": _iso_datetime(application.get("created_at")),
        "updated_at": _iso_datetime(application.get("updated_at")),
        "completed_at": _iso_datetime(application.get("completed_at")),
        "withdrawn_at": _iso_datetime(application.get("withdrawn_at")),
    }


def _freelancer_profile(freelancer_id: ObjectId) -> Optional[dict[str, Any]]:
    return _collection("freelancers").find_one({"_id": freelancer_id})


def create_application(
    payload: ApplicationCreate, freelancer_user: dict[str, Any]
) -> dict[str, Any]:
    """Submit one application for the authenticated freelancer.

    ``freelancer_user`` is the server-validated user. Any ``freelancer_id`` or
    ``status`` in the request body is ignored by the request model.
    """
    freelancer_id = _as_object_id(freelancer_user.get("id", ""))
    if freelancer_id is None:
        raise ApplicationPermissionError("Invalid freelancer account.")

    project_id = _as_object_id(payload.project_id)
    if project_id is None:
        raise ProjectNotFoundError("Project not found.")

    project = _collection("projects").find_one({"_id": project_id})
    if project is None:
        raise ProjectNotFoundError("Project not found.")
    if str(project.get("status") or "") != "open":
        raise ProjectNotOpenError(
            "This project is no longer accepting applications."
        )

    applications = _collection("applications")
    if applications.find_one(
        {"project_id": project_id, "freelancer_id": freelancer_id}
    ):
        raise DuplicateApplicationError(
            "You have already applied to this project."
        )

    profile = _freelancer_profile(freelancer_id)
    freelancer_snapshot = _stored_freelancer_snapshot(
        profile, freelancer_user
    )
    project_snapshot = _project_summary(project) or {}

    now = datetime.now(timezone.utc)
    application = {
        "_id": ObjectId(),
        "project_id": project_id,
        "project_title": project_snapshot.get("title") or "",
        "project_category": project_snapshot.get("category") or "",
        "project_snapshot": project_snapshot,
        "client_id": project.get("client_id"),
        "client_name": project_snapshot.get("client_name") or "",
        "freelancer_id": freelancer_id,
        "freelancer_name": freelancer_snapshot.get("name") or "",
        "freelancer_headline": freelancer_snapshot.get("headline") or "",
        "freelancer_snapshot": freelancer_snapshot,
        "cover_letter": payload.cover_letter,
        "bid_amount": float(payload.bid_amount),
        "currency": str(project.get("currency") or "USD"),
        "delivery_days": payload.delivery_days,
        "status": "pending",
        "rating": None,
        "review": None,
        "created_at": now,
        "updated_at": now,
        "completed_at": None,
    }

    try:
        applications.insert_one(application)
    except DuplicateKeyError as exc:
        # The unique (project_id, freelancer_id) index also protects races
        # between the pre-check above and this insert.
        raise DuplicateApplicationError(
            "You have already applied to this project."
        ) from exc

    return public_application(application, project=project, freelancer=profile)


def list_my_applications(
    user: dict[str, Any], *, limit: int
) -> tuple[list[dict[str, Any]], int]:
    """List applications visible to the authenticated user.

    Freelancers see every application they submitted, including withdrawn
    ones. Clients see applications received on projects they own, excluding
    withdrawn applications from the active list. The query is always scoped
    by the token, so one account can never read another account's applications.
    """
    user_id = _as_object_id(user.get("id", ""))
    if user_id is None:
        raise ApplicationPermissionError("Invalid account.")

    role = user.get("role")
    if role == "freelancer":
        query = {"freelancer_id": user_id}
    elif role == "client":
        query = {"client_id": user_id, "status": {"$ne": "withdrawn"}}
    else:
        raise ApplicationPermissionError(
            "You do not have permission to perform this action."
        )

    try:
        collection = _collection("applications")
        total = collection.count_documents(query)
        cursor = (
            collection.find(query)
            .sort([("created_at", DESCENDING), ("_id", ASCENDING)])
            .limit(limit)
        )
        return [public_application(application) for application in cursor], total
    except Exception as exc:
        # If the database is unreachable or any other DB error occurs, surface a 503.
        from fastapi import HTTPException
        raise HTTPException(status_code=503, detail="Database unavailable") from exc


def list_project_applications(
    project_id: str, client: dict[str, Any], *, limit: int
) -> tuple[list[dict[str, Any]], int]:
    """List applications for one project owned by the authenticated client."""
    object_id = _as_object_id(project_id)
    if object_id is None:
        raise ProjectNotFoundError("Project not found.")

    project = _collection("projects").find_one({"_id": object_id})
    if project is None:
        raise ProjectNotFoundError("Project not found.")

    client_id = _as_object_id(client.get("id", ""))
    if client_id is None or project.get("client_id") != client_id:
        raise ApplicationPermissionError(
            "You do not have permission to perform this action."
        )

    collection = _collection("applications")
    query = {"project_id": object_id, "status": {"$ne": "withdrawn"}}
    total = collection.count_documents(query)
    cursor = (
        collection.find(query)
        .sort([("created_at", DESCENDING), ("_id", ASCENDING)])
        .limit(limit)
    )
    return [
        public_application(application, project=project)
        for application in cursor
    ], total


def _reject_active_others(
    project_id: ObjectId, application_id: ObjectId, now: datetime
) -> None:
    """Close the remaining pending and shortlisted applications after a hire."""
    _collection("applications").update_many(
        {
            "project_id": project_id,
            "_id": {"$ne": application_id},
            "status": {"$in": ["pending", "shortlisted"]},
        },
        {
            "$set": {
                "status": "rejected",
                "updated_at": now,
                "project_snapshot.status": "in_progress",
            }
        },
    )


def _mark_project_completed(
    project_id: ObjectId,
    application_id: ObjectId,
    now: datetime,
    *,
    session: Any = None,
) -> Optional[dict[str, Any]]:
    """Move the hired project to completed, but only for the hired application."""
    kwargs: dict[str, Any] = {"return_document": ReturnDocument.AFTER}
    if session is not None:
        kwargs["session"] = session
    return _collection("projects").find_one_and_update(
        {
            "_id": project_id,
            "status": "in_progress",
            "hired_application_id": application_id,
        },
        {"$set": {"status": "completed", "updated_at": now}},
        **kwargs,
    )


def _mark_application_completed(
    application_id: ObjectId,
    now: datetime,
    *,
    session: Any = None,
    rating: Optional[int] = None,
    review: Optional[str] = None,
) -> Optional[dict[str, Any]]:
    """Move an accepted application to completed and record the UTC timestamp, rating and review."""
    kwargs: dict[str, Any] = {"return_document": ReturnDocument.AFTER}
    if session is not None:
        kwargs["session"] = session
    update_set = {
        "status": "completed",
        "completed_at": now,
        "updated_at": now,
        "project_snapshot.status": "completed",
    }
    if rating is not None:
        update_set["rating"] = rating
    if review is not None:
        update_set["review"] = review
    return _collection("applications").find_one_and_update(
        {"_id": application_id, "status": "accepted"},
        {"$set": update_set},
        **kwargs,
    )


def _rollback_project_completion(
    project_id: ObjectId,
    application_id: ObjectId,
    now: datetime,
) -> None:
    """Undo the project half of a completion when the application update fails."""
    _collection("projects").update_one(
        {
            "_id": project_id,
            "status": "completed",
            "hired_application_id": application_id,
        },
        {"$set": {"status": "in_progress", "updated_at": now}},
    )


def _run_completion_transaction(
    project_id: ObjectId,
    application_id: ObjectId,
    now: datetime,
    *,
    rating: Optional[int] = None,
    review: Optional[str] = None,
) -> Optional[tuple[dict[str, Any], dict[str, Any]]]:

    """Complete both documents atomically when MongoDB supports transactions."""

    def work(session: Any) -> tuple[dict[str, Any], dict[str, Any]]:
        project = _mark_project_completed(
            project_id, application_id, now, session=session
        )
        if project is None:
            raise ApplicationConflictError(
                "Only the hired application on an in-progress project can "
                "be completed."
            )
        application = _mark_application_completed(
            application_id, now, session=session, rating=rating, review=review
        )
        if application is None:
            raise ApplicationConflictError(
                "This application is no longer accepted."
            )
        return application, project

    try:
        with get_database().client.start_session() as session:
            with session.start_transaction():
                return work(session)
    except NotImplementedError:
        # mongomock and some lightweight MongoDB-compatible servers do not
        # implement sessions/transactions. Use the compensating path below.
        return None
    except OperationFailure as exc:
        if exc.code in TRANSACTION_UNSUPPORTED_CODES:
            return None
        raise


def _complete_application(
    application: dict[str, Any],
    client_id: ObjectId,
    current_status: str,
    *,
    rating: Optional[int] = None,
    review: Optional[str] = None,
) -> dict[str, Any]:

    """Complete the hired application and its project consistently."""
    application_id = application["_id"]
    project_id = application.get("project_id")
    if not isinstance(project_id, ObjectId):
        raise ProjectNotFoundError("Project not found.")

    project = _collection("projects").find_one({"_id": project_id})
    if project is None:
        raise ProjectNotFoundError("Project not found.")
    if project.get("client_id") != client_id:
        raise ApplicationPermissionError(
            "You do not have permission to perform this action."
        )

    now = datetime.now(timezone.utc)

    if current_status == "completed":
        # Repeating completion is harmless. Repair the project half if an
        # earlier non-transactional attempt stopped after completing the app.
        if project.get("status") == "completed":
            return public_application(application, project=project)
        if (
            project.get("status") == "in_progress"
            and project.get("hired_application_id") == application_id
        ):
            repaired_project = _mark_project_completed(
                project_id, application_id, now
            )
            if repaired_project is None:
                raise ApplicationConflictError(
                    "This project is not in progress."
                )
            return public_application(application, project=repaired_project)
        raise ApplicationConflictError(
            "This application cannot be completed in the project's current "
            "state."
        )

    if current_status != "accepted":
        raise ApplicationConflictError(
            "Only an accepted application can be completed."
        )

    if project.get("hired_application_id") != application_id:
        raise ApplicationConflictError(
            "Only the hired application for this project can be completed."
        )

    if project.get("status") == "completed":
        # Repair the application half if an earlier non-transactional attempt
        # stopped after completing the project.
        repaired_application = _mark_application_completed(application_id, now, rating=rating, review=review)
        if repaired_application is None:
            raise ApplicationConflictError(
                "This application is no longer accepted."
            )
        return public_application(repaired_application, project=project)

    if project.get("status") != "in_progress":
        raise ApplicationConflictError("This project is not in progress.")

    completed = _run_completion_transaction(project_id, application_id, now, rating=rating, review=review)
    if completed is not None:
        completed_application, completed_project = completed
        return public_application(
            completed_application, project=completed_project
        )

    # Compensating path for deployments without transaction support. The
    # project is updated first so a failed application update cannot leave an
    # application completed while its project is still in progress.
    completed_project = _mark_project_completed(project_id, application_id, now)
    if completed_project is None:
        raise ApplicationConflictError("This project is not in progress.")
    try:
        completed_application = _mark_application_completed(application_id, now, rating=rating, review=review)
        if completed_application is None:
            raise ApplicationConflictError(
                "This application is no longer accepted."
            )
    except Exception:
        _rollback_project_completion(project_id, application_id, now)
        raise

    return public_application(completed_application, project=completed_project)


def withdraw_application(application_id: str, freelancer: dict) -> dict[str, Any]:
    """Freelancer withdraws their own pending or shortlisted application.

    The application document is kept. A second withdrawal of the same
    application returns the existing withdrawn record and does not change
    ``withdrawn_at``.
    """
    if freelancer.get("role") != "freelancer":
        raise ApplicationPermissionError(
            "You do not have permission to perform this action."
        )

    object_id = _as_object_id(application_id)
    if object_id is None:
        raise ApplicationNotFoundError("Application not found.")

    applications = _collection("applications")
    application = applications.find_one({"_id": object_id})
    if application is None:
        raise ApplicationNotFoundError("Application not found.")

    freelancer_id = _as_object_id(freelancer.get("id", ""))
    if freelancer_id is None or application.get("freelancer_id") != freelancer_id:
        raise ApplicationPermissionError(
            "You do not have permission to perform this action."
        )

    current_status = str(application.get("status") or "pending")
    if current_status == "withdrawn":
        return public_application(application)

    if current_status not in ("pending", "shortlisted"):
        raise ApplicationConflictError(
            "Only pending or shortlisted applications can be withdrawn."
        )

    now = datetime.now(timezone.utc)
    updated = applications.find_one_and_update(
        {
            "_id": object_id,
            "freelancer_id": freelancer_id,
            "status": {"$in": ["pending", "shortlisted"]},
        },
        {"$set": {"status": "withdrawn", "withdrawn_at": now, "updated_at": now}},
        return_document=ReturnDocument.AFTER,
    )
    if updated is None:
        latest = applications.find_one({"_id": object_id})
        if (
            latest is not None
            and latest.get("freelancer_id") == freelancer_id
            and str(latest.get("status") or "") == "withdrawn"
        ):
            return public_application(latest)
        raise ApplicationConflictError(
            "Only pending or shortlisted applications can be withdrawn."
        )
    return public_application(updated)

def update_application_status(
    application_id: str,
    payload: ApplicationStatusUpdate,
    client: dict[str, Any],
) -> dict[str, Any]:
    """Shortlist, accept, or reject one application as the owning client.

    Shortlisting only changes the application. Acceptance is the single-hire
    transition. It moves the project to ``in_progress``, records
    ``hired_application_id``, rejects every other pending or shortlisted
    application, and refuses any later hire for the same project.
    """
    object_id = _as_object_id(application_id)
    if object_id is None:
        raise ApplicationNotFoundError("Application not found.")

    applications = _collection("applications")
    application = applications.find_one({"_id": object_id})
    if application is None:
        raise ApplicationNotFoundError("Application not found.")

    client_id = _as_object_id(client.get("id", ""))
    if client_id is None or application.get("client_id") != client_id:
        raise ApplicationPermissionError(
            "You do not have permission to perform this action."
        )

    current_status = str(application.get("status") or "pending")
    requested_status = payload.status

    if current_status == "withdrawn" or requested_status == "withdrawn":
        raise ApplicationConflictError(
            "This application has been withdrawn and can no longer be updated."
        )

    if requested_status == "completed":
        return _complete_application(application, client_id, current_status, rating=payload.rating, review=payload.review)

    if current_status == requested_status:
        # Repeating the same decision is harmless and keeps the UI simple.
        return public_application(application)

    if current_status not in ("pending", "shortlisted"):
        raise ApplicationConflictError(
            "This application has already been finalised."
        )

    now = datetime.now(timezone.utc)

    if requested_status == "shortlisted":
        updated = applications.find_one_and_update(
            {"_id": object_id, "status": "pending"},
            {"$set": {"status": "shortlisted", "updated_at": now}},
            return_document=ReturnDocument.AFTER,
        )
        if updated is None:
            raise ApplicationConflictError(
                "This application has already been finalised."
            )
        return public_application(updated)

    if requested_status == "rejected":
        updated = applications.find_one_and_update(
            {"_id": object_id, "status": current_status},
            {"$set": {"status": "rejected", "updated_at": now}},
            return_document=ReturnDocument.AFTER,
        )
        if updated is None:
            raise ApplicationConflictError(
                "This application has already been finalised."
            )
        return public_application(updated)

    # requested_status == "accepted" because the model validates the literal.
    project_id = application.get("project_id")
    project = _collection("projects").find_one({"_id": project_id})
    if project is None:
        raise ProjectNotFoundError("Project not found.")

    if str(project.get("status") or "") != "open":
        raise ApplicationConflictError(
            "This project is not open for hiring."
        )

    hired_application_id = project.get("hired_application_id")
    if (
        hired_application_id is not None
        and hired_application_id != object_id
    ):
        raise ApplicationConflictError(
            "Another freelancer has already been hired for this project."
        )

    already_hired = applications.find_one(
        {
            "project_id": project_id,
            "status": "accepted",
            "_id": {"$ne": object_id},
        }
    )
    if already_hired is not None:
        raise ApplicationConflictError(
            "Another freelancer has already been hired for this project."
        )

    # Claim the project first. The status filter makes two concurrent accepts
    # race safely: only one update can match ``status == "open"``.
    claim = _collection("projects").update_one(
        {"_id": project_id, "status": "open"},
        {
            "$set": {
                "status": "in_progress",
                "hired_application_id": object_id,
                "hired_freelancer_id": application.get("freelancer_id"),
                "updated_at": now,
            }
        },
    )
    if claim.modified_count != 1:
        raise ApplicationConflictError(
            "This project is not open for hiring."
        )

    try:
        updated = applications.find_one_and_update(
            {"_id": object_id, "status": current_status},
            {
                "$set": {
                    "status": "accepted",
                    "updated_at": now,
                    "project_snapshot.status": "in_progress",
                }
            },
            return_document=ReturnDocument.AFTER,
        )
        if updated is None:
            raise ApplicationConflictError(
                "This application has already been finalised."
            )
        _reject_active_others(project_id, object_id, now)
    except Exception:
        # Restore the project so a failed hire cannot leave it locked.
        _collection("projects").update_one(
            {"_id": project_id, "hired_application_id": object_id},
            {
                "$set": {"status": "open", "updated_at": now},
                "$unset": {"hired_application_id": "", "hired_freelancer_id": ""},
            },
        )
        raise

    project["status"] = "in_progress"
    project["hired_application_id"] = object_id
    return public_application(updated, project=project)
