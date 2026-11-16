"""Application submission, shortlist/review, and single-hire routes.

The freelancer identity and application status are always derived from the
JWT and from the server-side workflow, never from request fields.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status

from Backend.dependencies import get_current_user, require_role
from Backend.models.application import (
    ApplicationCreate,
    ApplicationListResponse,
    ApplicationPublic,
    ApplicationStatusUpdate,
)
from Backend.services.application_service import (
    ApplicationConflictError,
    ApplicationNotFoundError,
    ApplicationPermissionError,
    DuplicateApplicationError,
    ProjectNotFoundError,
    ProjectNotOpenError,
    create_application,
    list_my_applications,
    list_project_applications,
    update_application_status,
    withdraw_application,
)

router = APIRouter(prefix="/applications", tags=["applications"])
project_applications_router = APIRouter(prefix="/projects", tags=["applications"])

PERMISSION_DETAIL = "You do not have permission to perform this action."


def _raise_application_error(exc: Exception) -> None:
    """Translate service exceptions into consistent HTTP responses."""
    if isinstance(exc, ProjectNotFoundError):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found.",
        ) from exc
    if isinstance(exc, ApplicationNotFoundError):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Application not found.",
        ) from exc
    if isinstance(exc, ApplicationPermissionError):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=PERMISSION_DETAIL,
        ) from exc
    if isinstance(exc, DuplicateApplicationError):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="You have already applied to this project.",
        ) from exc
    if isinstance(exc, ProjectNotOpenError):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This project is no longer accepting applications.",
        ) from exc
    if isinstance(exc, ApplicationConflictError):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc) or "This application cannot be updated.",
        ) from exc
    raise exc


@router.post(
    "",
    response_model=ApplicationPublic,
    status_code=status.HTTP_201_CREATED,
    summary="Apply to an open project",
    description=(
        "Submit one application to an existing open project. The freelancer "
        "identity comes from the bearer token; any `freelancer_id` or "
        "`status` in the body is ignored. A freelancer can apply to the same "
        "project only once. New applications always start as `pending`."
    ),
    responses={
        201: {"description": "Application created with status pending."},
        401: {"description": "Authentication required."},
        403: {"description": "Only freelancers may apply."},
        404: {"description": "Project not found."},
        409: {
            "description": (
                "Project is not open or this freelancer already applied."
            )
        },
        422: {"description": "Invalid request body."},
    },
)
def create_application_route(
    payload: ApplicationCreate,
    current_user: dict = Depends(require_role("freelancer")),
) -> dict:
    try:
        return create_application(payload, current_user)
    except Exception as exc:  # noqa: BLE001 - mapped to HTTP below
        _raise_application_error(exc)


@router.get(
    "/my",
    response_model=ApplicationListResponse,
    summary="List my applications",
    description=(
        "Return applications visible to the authenticated account. A "
        "freelancer receives the applications they submitted; a client "
        "receives applications on projects they own. Results are newest "
        "first and always scoped by the token."
    ),
    responses={
        200: {"description": "Applications visible to the current user."},
        401: {"description": "Authentication required."},
        403: {"description": "Unsupported account role."},
    },
)
def list_my_applications_route(
    limit: int = Query(50, ge=1, le=500),
    current_user: dict = Depends(get_current_user),
) -> dict:
    try:
        items, total = list_my_applications(current_user, limit=limit)
    except Exception as exc:  # noqa: BLE001 - mapped to HTTP below
        _raise_application_error(exc)
    return {"items": items, "total": total}


@project_applications_router.get(
    "/{project_id}/applications",
    response_model=ApplicationListResponse,
    summary="List applications for a project",
    description=(
        "Return every application submitted to a project. Only the client "
        "who owns the project may call this endpoint."
    ),
    responses={
        200: {"description": "Applications for the owned project."},
        401: {"description": "Authentication required."},
        403: {"description": "Only the owning client may view applicants."},
        404: {"description": "Project not found."},
    },
)
def list_project_applications_route(
    project_id: str,
    limit: int = Query(200, ge=1, le=500),
    current_user: dict = Depends(require_role("client")),
) -> dict:
    try:
        items, total = list_project_applications(
            project_id, current_user, limit=limit
        )
    except Exception as exc:  # noqa: BLE001 - mapped to HTTP below
        _raise_application_error(exc)
    return {"items": items, "total": total}


def _update_status(
    application_id: str,
    payload: ApplicationStatusUpdate,
    current_user: dict,
) -> dict:
    try:
        return update_application_status(application_id, payload, current_user)
    except Exception as exc:  # noqa: BLE001 - mapped to HTTP below
        _raise_application_error(exc)


@router.patch(
    "/{application_id}/status",
    response_model=ApplicationPublic,
    summary="Shortlist, accept, reject, or complete an application",
    description=(
        "The owning client may shortlist, accept, or reject a pending or "
        "shortlisted application. Accepting hires that freelancer, moves the "
        "project to `in_progress`, records the hired application, and "
        "auto-rejects the remaining pending and shortlisted applications. A "
        "project can have only one hired freelancer; later accepts return "
        "409. Only the hired, accepted application may be completed, which "
        "moves both the application and project to `completed`. Repeating "
        "the same status is idempotent."
    ),
    responses={
        200: {"description": "Application status updated."},
        401: {"description": "Authentication required."},
        403: {"description": "Only the owning client may decide."},
        404: {"description": "Application or project not found."},
        409: {"description": "The transition would create an invalid state."},
        422: {
            "description": (
                "Status must be shortlisted, accepted, rejected, or completed."
            )
        },
    },
)
def update_application_status_route(
    application_id: str,
    payload: ApplicationStatusUpdate,
    current_user: dict = Depends(require_role("client")),
) -> dict:
    return _update_status(application_id, payload, current_user)

# New withdrawal endpoint for freelancers
@router.post(
    "/{application_id}/withdraw",
    response_model=ApplicationPublic,
    summary="Freelancer withdraws a pending or shortlisted application",
    description=(
        "Only the owning freelancer may withdraw their own application. "
        "Allowed when the application status is `pending` or `shortlisted`."
    ),
    responses={
        200: {"description": "Application withdrawn successfully."},
        401: {"description": "Authentication required."},
        403: {"description": "You do not have permission to withdraw this application."},
        404: {"description": "Application not found."},
        409: {"description": "Withdrawal not allowed in the current state."},
    },
)
def withdraw_application_route(
    application_id: str,
    current_user: dict = Depends(require_role("freelancer")),
) -> dict:
    try:
        return withdraw_application(application_id, current_user)
    except Exception as exc:
        _raise_application_error(exc)


@router.put(
    "/{application_id}/status",
    response_model=ApplicationPublic,
    include_in_schema=False,
)
def update_application_status_compat_route(
    application_id: str,
    payload: ApplicationStatusUpdate,
    current_user: dict = Depends(require_role("client")),
) -> dict:
    """Compatibility alias for Frontend(2), which sends PUT for status."""
    return _update_status(application_id, payload, current_user)

# New withdrawal endpoint for freelancers
@router.post(
    "/{application_id}/withdraw",
    response_model=ApplicationPublic,
    summary="Freelancer withdraws a pending or shortlisted application",
    description=(
        "Only the owning freelancer may withdraw their own application. "
        "Allowed when the application status is `pending` or `shortlisted`."
    ),
    responses={
        200: {"description": "Application withdrawn successfully."},
        401: {"description": "Authentication required."},
        403: {"description": "You do not have permission to withdraw this application."},
        404: {"description": "Application not found."},
        409: {"description": "Withdrawal not allowed in the current state."},
    },
)
def withdraw_application_route(
    application_id: str,
    current_user: dict = Depends(require_role("freelancer")),
) -> dict:
    try:
        return withdraw_application(application_id, current_user)
    except Exception as exc:
        _raise_application_error(exc)
