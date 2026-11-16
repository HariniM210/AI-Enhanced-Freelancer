"""Application request and response models.

The browser never supplies the freelancer identity or the initial status.
Both are set by the server from the JWT and from the application workflow.
"""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import AliasChoices, BaseModel, ConfigDict, Field


class ApplicationCreate(BaseModel):
    """Payload sent by Frontend(2)/js/project-details.js.

    ``proposal`` and ``proposed_budget`` are accepted as aliases so the API is
    usable from either the frontend contract or the academic specification.
    """

    model_config = ConfigDict(
        extra="ignore",
        str_strip_whitespace=True,
        populate_by_name=True,
        json_schema_extra={
            "example": {
                "project_id": "66f1a2b3c4d5e6f7a8b9c0d2",
                "cover_letter": (
                    "I have built several production FastAPI services with "
                    "MongoDB and can deliver this project on time with tests "
                    "and documentation."
                ),
                "bid_amount": 1500,
                "delivery_days": 21,
            }
        },
    )

    project_id: str = Field(
        min_length=1,
        max_length=100,
        description="ObjectId of an existing open project.",
    )
    cover_letter: str = Field(
        min_length=50,
        max_length=2000,
        validation_alias=AliasChoices("cover_letter", "proposal"),
        description="The freelancer's proposal or cover letter.",
    )
    bid_amount: float = Field(
        ge=1,
        allow_inf_nan=False,
        validation_alias=AliasChoices("bid_amount", "proposed_budget"),
        description="The freelancer's proposed budget for the project.",
    )
    delivery_days: Optional[int] = Field(
        default=None,
        ge=1,
        le=730,
        description="Optional delivery estimate in days.",
    )


class ApplicationStatusUpdate(BaseModel):
    """Client decision on an application, optionally including rating and review when completing."""

    model_config = ConfigDict(
        extra="ignore",
        json_schema_extra={"example": {"status": "accepted", "rating": 5, "review": "Great work!"}},
    )

    status: Literal["shortlisted", "accepted", "rejected", "completed"] = Field(
        description=(
            "Use shortlisted to shortlist this applicant, accepted to hire "
            "them, rejected to decline, completed to close out an "
            "accepted hire."
        )
    )
    rating: Optional[int] = Field(
        default=None,
        description="1‑5 star rating supplied when marking the application as completed.",
        ge=1,
        le=5,
    )
    review: Optional[str] = Field(
        default=None,
        description="Optional textual review supplied when completing the application.",
    )


class ApplicationProjectSummary(BaseModel):
    """Project information embedded in an application response."""

    id: str
    title: str
    category: str
    budget_min: Optional[float] = None
    budget_max: Optional[float] = None
    currency: str
    budget_type: str
    deadline: Optional[str] = None
    status: str
    client_name: str


class ApplicationFreelancerSummary(BaseModel):
    """Public applicant details suitable for client review.

    Email, password hashes, and authentication fields are deliberately absent.
    """

    id: str
    name: str
    headline: str
    summary: str = ""
    location: str = ""
    availability: str = ""
    skills: list[str] = Field(default_factory=list)
    years_experience: Optional[int] = None
    experience_level: Optional[str] = None
    hourly_rate: Optional[float] = None
    currency: str = "USD"
    avg_rating: float = 0.0
    reviews_count: int = 0
    completed_projects: int = 0
    avatar_url: Optional[str] = None


class ApplicationPublic(BaseModel):
    """Application shape returned by every Phase 4 endpoint."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "id": "66f1a2b3c4d5e6f7a8b9c0d1",
                "project_id": "66f1a2b3c4d5e6f7a8b9c0d2",
                "project_title": "Build a REST API for logistics",
                "project_category": "Backend & APIs",
                "client_id": "66f1a2b3c4d5e6f7a8b9c0d3",
                "client_name": "Northwind Logistics",
                "freelancer_id": "66f1a2b3c4d5e6f7a8b9c0d4",
                "freelancer_name": "Aarav Sharma",
                "freelancer_headline": "Full-stack developer",
                "freelancer": {
                    "id": "66f1a2b3c4d5e6f7a8b9c0d4",
                    "name": "Aarav Sharma",
                    "headline": "Full-stack developer",
                    "summary": "I build secure FastAPI services.",
                    "location": "Pune, India",
                    "availability": "Available now",
                    "skills": ["Python", "FastAPI", "MongoDB"],
                    "years_experience": 3,
                    "experience_level": "Intermediate",
                    "hourly_rate": 35.0,
                    "currency": "USD",
                    "avg_rating": 4.8,
                    "reviews_count": 12,
                    "completed_projects": 9,
                    "avatar_url": None,
                },
                "project": {
                    "id": "66f1a2b3c4d5e6f7a8b9c0d2",
                    "title": "Build a REST API for logistics",
                    "category": "Backend & APIs",
                    "budget_min": 1200.0,
                    "budget_max": 2000.0,
                    "currency": "USD",
                    "budget_type": "fixed",
                    "deadline": "2026-12-20",
                    "status": "open",
                    "client_name": "Northwind Logistics",
                },
                "cover_letter": (
                    "I have built similar FastAPI services and can deliver "
                    "this in three weeks."
                ),
                "bid_amount": 1500.0,
                "currency": "USD",
                "delivery_days": 21,
                "status": "pending",
                "rating": None,
                "review": None,
                "created_at": "2026-11-12T10:00:00+00:00",
                "updated_at": "2026-11-12T10:00:00+00:00",
                "completed_at": None,
            }
        }
    )

    id: str
    project_id: str
    project_title: str
    project_category: str
    client_id: Optional[str] = None
    client_name: str
    freelancer_id: str
    freelancer_name: str
    freelancer_headline: str
    freelancer: Optional[ApplicationFreelancerSummary] = None
    project: Optional[ApplicationProjectSummary] = None
    cover_letter: str
    bid_amount: float
    currency: str
    delivery_days: Optional[int] = None
    status: str = Field(
        description=(
            "Applications start as pending and may move to shortlisted, "
            "accepted, rejected, or completed. Rating and review remain "
            "reserved for a later phase."
        )
    )
    rating: Optional[int] = None
    review: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    completed_at: Optional[str] = None


class ApplicationListResponse(BaseModel):
    """List envelope understood by Frontend(2)/js/api.js -> Api.asList()."""

    items: list[ApplicationPublic]
    total: int
