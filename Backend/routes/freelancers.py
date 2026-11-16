"""Freelancer profile routes.

GET endpoints are public so clients can browse talent. Only a logged-in
freelancer can update the profile identified by their own token.
"""

from __future__ import annotations

from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status

from Backend.dependencies import require_role
from Backend.models.freelancer import (
    FreelancerListResponse,
    FreelancerProfileUpdate,
    FreelancerPublic,
)
from Backend.services.freelancer_service import (
    get_freelancer_profile,
    list_freelancers,
    public_freelancer,
    update_freelancer_profile,
)

router = APIRouter(prefix="/freelancers", tags=["freelancers"])


@router.get(
    "",
    response_model=FreelancerListResponse,
    summary="List freelancer profiles",
)
def list_freelancers_route(
    limit: int = Query(20, ge=1, le=100),
    sort: Optional[Literal["rating", "recent"]] = Query(None),
    skills: Optional[str] = Query(None, max_length=500),
    q: Optional[str] = Query(None, max_length=100),
) -> dict:
    skill_list = [
        skill.strip() for skill in (skills or "").split(",") if skill.strip()
    ]
    items, total = list_freelancers(
        limit=limit, sort=sort, skills=skill_list, q=q
    )
    return {"items": items, "total": total}


@router.put(
    "/profile",
    response_model=FreelancerPublic,
    summary="Update the authenticated freelancer's profile",
)
def update_profile(
    payload: FreelancerProfileUpdate,
    current_user: dict = Depends(require_role("freelancer")),
) -> dict:
    profile = update_freelancer_profile(current_user["id"], payload)
    if profile is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Freelancer profile not found.",
        )
    return public_freelancer(profile)


@router.get(
    "/{freelancer_id}",
    response_model=FreelancerPublic,
    summary="Get a freelancer profile",
)
def get_freelancer(freelancer_id: str) -> dict:
    # Healing a missing profile keeps older accounts usable. It only happens
    # when the id belongs to an existing freelancer user.
    profile = get_freelancer_profile(freelancer_id, create_if_missing=True)
    if profile is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Freelancer profile not found.",
        )
    return public_freelancer(profile)
