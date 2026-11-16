"""Project creation request and public response models.

The client identity (``client_id`` / ``client_name``) and the initial
``status`` are never accepted from the browser. They come from the JWT and
from the server, which prevents one client from posting a project on behalf
of another.
"""

from __future__ import annotations

import re
from datetime import date
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from Backend.utils.validation import clean_string_list


class ProjectCreate(BaseModel):
    """Payload sent by Frontend(2)/js/post-project.js."""

    model_config = ConfigDict(extra="ignore", str_strip_whitespace=True)

    title: str = Field(min_length=10, max_length=120)
    category: str = Field(
        min_length=1,
        max_length=80,
        description=(
            "Project category. The frontend supplies values from "
            "REF.categories; validation stays permissive so existing projects "
            "and legacy category names remain valid."
        ),
    )
    description: str = Field(min_length=80, max_length=5000)
    skills: list[str]
    experience_level: Literal["Entry", "Intermediate", "Expert"]
    budget_type: Literal["fixed", "hourly"]
    budget_min: float = Field(ge=1)
    budget_max: float = Field(ge=1)
    currency: str = Field(min_length=3, max_length=3)
    deadline: date
    duration: Optional[str] = Field(default=None, max_length=80)
    requirements: Optional[list[str]] = None
    deliverables: Optional[list[str]] = None
    location: Optional[str] = Field(default=None, max_length=120)

    @field_validator("skills")
    @classmethod
    def validate_skills(cls, value: list[str]) -> list[str]:
        cleaned = clean_string_list(value, max_items=12, max_length=50)
        if not cleaned:
            raise ValueError("Add at least one required skill.")
        return cleaned

    @field_validator("requirements", "deliverables")
    @classmethod
    def validate_lines(
        cls, value: Optional[list[str]]
    ) -> Optional[list[str]]:
        if value is None:
            return None
        return clean_string_list(
            value, max_items=50, max_length=300, dedupe=False
        )

    @field_validator("currency")
    @classmethod
    def validate_currency(cls, value: str) -> str:
        value = value.upper()
        if not re.fullmatch(r"[A-Z]{3}", value):
            raise ValueError("Currency must be a 3-letter code such as USD.")
        return value

    @field_validator("deadline")
    @classmethod
    def validate_deadline(cls, value: date) -> date:
        if value < date.today():
            raise ValueError("Choose a date in the future.")
        return value

    @field_validator("duration", "location")
    @classmethod
    def empty_string_to_none(cls, value: Optional[str]) -> Optional[str]:
        return value or None

    @model_validator(mode="after")
    def validate_budget_range(self):
        if self.budget_max < self.budget_min:
            raise ValueError("Maximum budget cannot be lower than the minimum.")
        return self


class ProjectPublic(BaseModel):
    """Project shape expected by the marketplace and project-details pages."""

    id: str
    title: str
    description: str
    category: str
    skills: list[str]
    budget_min: Optional[float] = None
    budget_max: Optional[float] = None
    currency: str
    budget_type: str
    deadline: Optional[str] = None
    duration: Optional[str] = None
    experience_level: Optional[str] = None
    status: str
    client_id: Optional[str] = None
    client_name: str
    location: str
    requirements: list[str]
    deliverables: list[str]
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    applications_count: int


class ProjectListResponse(BaseModel):
    """List envelope understood by Frontend(2)/js/api.js -> Api.asList()."""

    items: list[ProjectPublic]
    total: int
