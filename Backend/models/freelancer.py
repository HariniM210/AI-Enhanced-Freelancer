"""Freelancer profile request and response models.

Only fields a freelancer is allowed to edit are accepted. System-managed
values (``avg_rating``, ``reviews_count`` and ``completed_projects``) are
deliberately absent, so a profile update can never award a rating.

``exclude_unset=True`` in the service is what makes this a true partial
update: the AI summary page sends only ``{"summary": "..."}`` and every other
profile field is left untouched.
"""

from __future__ import annotations

import re
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from Backend.utils.validation import clean_string_list

HTTP_URL_RE = re.compile(r"^https?://", re.IGNORECASE)


class PortfolioItem(BaseModel):
    """One portfolio entry sent by the profile edit form."""

    model_config = ConfigDict(extra="ignore", str_strip_whitespace=True)

    title: str = Field(min_length=1, max_length=120)
    description: Optional[str] = Field(default=None, max_length=1000)
    url: Optional[str] = Field(default=None, max_length=500)
    # ``None`` means "not sent by the edit form"; the service preserves the
    # existing technologies in that case.
    technologies: Optional[list[str]] = Field(default=None, max_length=20)

    @field_validator("url")
    @classmethod
    def validate_url(cls, value: Optional[str]) -> Optional[str]:
        if value is None or not value.strip():
            return None
        if not HTTP_URL_RE.match(value):
            raise ValueError("Portfolio links must start with http:// or https://.")
        return value

    @field_validator("technologies")
    @classmethod
    def validate_technologies(
        cls, value: Optional[list[str]]
    ) -> Optional[list[str]]:
        if value is None:
            return None
        return clean_string_list(value, max_items=20, max_length=50)


class WorkHistoryItem(BaseModel):
    """One work-history entry sent by the profile edit form."""

    model_config = ConfigDict(extra="ignore", str_strip_whitespace=True)

    role: str = Field(min_length=1, max_length=120)
    company: Optional[str] = Field(default=None, max_length=120)
    period: Optional[str] = Field(default=None, max_length=80)
    # ``None`` means "not sent by the edit form"; the service preserves the
    # existing description in that case.
    description: Optional[str] = Field(default=None, max_length=1000)


class FreelancerProfileUpdate(BaseModel):
    """Any subset of the editable freelancer profile fields."""

    model_config = ConfigDict(extra="ignore", str_strip_whitespace=True)

    name: Optional[str] = Field(default=None, min_length=2, max_length=80)
    headline: Optional[str] = Field(default=None, min_length=3, max_length=100)
    summary: Optional[str] = Field(default=None, max_length=5000)
    location: Optional[str] = Field(default=None, max_length=120)
    availability: Optional[
        Literal[
            "Available now",
            "Available in 2 weeks",
            "Part-time only",
            "Not available",
        ]
    ] = None
    years_experience: Optional[int] = Field(default=None, ge=0, le=60)
    experience_level: Optional[Literal["Entry", "Intermediate", "Expert"]] = None
    hourly_rate: Optional[float] = Field(default=None, ge=1)
    currency: Optional[str] = Field(default=None, min_length=3, max_length=3)
    avatar_url: Optional[str] = Field(default=None, max_length=500)
    skills: Optional[list[str]] = None
    portfolio: Optional[list[PortfolioItem]] = Field(default=None, max_length=50)
    work_history: Optional[list[WorkHistoryItem]] = Field(default=None, max_length=50)

    @field_validator("currency")
    @classmethod
    def validate_currency(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        value = value.upper()
        if not re.fullmatch(r"[A-Z]{3}", value):
            raise ValueError("Currency must be a 3-letter code such as USD.")
        return value

    @field_validator("avatar_url")
    @classmethod
    def validate_avatar_url(cls, value: Optional[str]) -> Optional[str]:
        if value is None or not value.strip():
            return None
        if not HTTP_URL_RE.match(value):
            raise ValueError("Avatar URL must start with http:// or https://.")
        return value

    @field_validator("skills")
    @classmethod
    def validate_skills(cls, value: Optional[list[str]]) -> Optional[list[str]]:
        if value is None:
            return None
        return clean_string_list(value, max_items=25, max_length=50)

    @model_validator(mode="after")
    def reject_explicit_null_for_required_fields(self):
        """Allow ``null`` only for fields that make sense to clear."""
        required_fields = (
            "name",
            "headline",
            "availability",
            "years_experience",
            "experience_level",
            "currency",
        )
        for field_name in required_fields:
            if field_name in self.model_fields_set and getattr(self, field_name) is None:
                raise ValueError(f"{field_name} cannot be null.")
        return self


class PortfolioItemPublic(BaseModel):
    """Portfolio shape returned to the browser."""

    title: str
    description: str = ""
    url: Optional[str] = None
    technologies: list[str] = Field(default_factory=list)


class WorkHistoryItemPublic(BaseModel):
    """Work-history shape returned to the browser."""

    role: str
    company: str = ""
    period: str = ""
    description: str = ""


class FreelancerPublic(BaseModel):
    """Public freelancer profile. Email and auth fields are never included."""

    id: str
    name: str
    headline: str
    summary: str
    location: str
    availability: str
    skills: list[str]
    years_experience: Optional[int] = None
    experience_level: str
    hourly_rate: Optional[float] = None
    currency: str
    avg_rating: float
    reviews_count: int
    completed_projects: int
    avatar_url: Optional[str] = None
    portfolio: list[PortfolioItemPublic]
    work_history: list[WorkHistoryItemPublic]


class FreelancerListResponse(BaseModel):
    """List envelope understood by Frontend(2)/js/api.js -> Api.asList()."""

    items: list[FreelancerPublic]
    total: int
