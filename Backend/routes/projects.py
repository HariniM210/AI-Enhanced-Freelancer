"""Client project routes.

Posting is restricted to clients. Browsing is public, but ``mine=true``
requires a client token so the response only contains that client's work.
"""

from __future__ import annotations

from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status

from Backend.dependencies import get_optional_current_user, require_role
from Backend.models.project import (
    ProjectCreate,
    ProjectListResponse,
    ProjectPublic,
)
from Backend.services.project_service import (
    create_project,
    get_project,
    list_projects,
    public_project,
)

router = APIRouter(prefix="/projects", tags=["projects"])

ProjectStatus = Literal["open", "in_progress", "completed", "closed"]
ProjectSort = Literal["recent", "deadline"]


@router.post(
    "",
    response_model=ProjectPublic,
    status_code=status.HTTP_201_CREATED,
    summary="Post a new project",
)
def create_project_route(
    payload: ProjectCreate,
    current_user: dict = Depends(require_role("client")),
) -> dict:
    return public_project(create_project(payload, current_user))


@router.get(
    "",
    response_model=ProjectListResponse,
    summary="List projects",
)
def list_projects_route(
    mine: bool = Query(False),
    project_status: Optional[ProjectStatus] = Query(None, alias="status"),
    limit: int = Query(20, ge=1, le=100),
    sort: ProjectSort = Query("recent"),
    current_user: Optional[dict] = Depends(get_optional_current_user),
) -> dict:
    if mine:
        if current_user is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication required.",
                headers={"WWW-Authenticate": "Bearer"},
            )
        if current_user.get("role") != "client":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to perform this action.",
            )

    items, total = list_projects(
        mine=mine,
        status=project_status,
        limit=limit,
        sort=sort,
        client_id=current_user.get("id") if mine and current_user else None,
    )
    return {"items": items, "total": total}


@router.get(
    "/{project_id}",
    response_model=ProjectPublic,
    summary="Get a project",
)
def get_project_route(project_id: str) -> dict:
    project = get_project(project_id)
    if project is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found.",
        )
    return project
