"""Phase 6 AI request and response models.

The browser supplies ids and writing preferences only. Profile and project
facts are always loaded from MongoDB by the server, so a caller cannot make
the model treat unverified profile claims as authoritative.
"""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from Backend.utils.validation import clean_string_list

Tone = Literal["Professional", "Friendly", "Confident", "Concise"]
Length = Literal["short", "medium", "detailed"]


class ProposalRequest(BaseModel):
    """Payload accepted by ``POST /ai/generate-proposal``."""

    model_config = ConfigDict(
        extra="ignore",
        str_strip_whitespace=True,
        json_schema_extra={
            "example": {
                "project_id": "66f1a2b3c4d5e6f7a8b9c0d2",
                "freelancer_id": "66f1a2b3c4d5e6f7a8b9c0d4",
                "tone": "Professional",
                "length": "medium",
                "highlights": "Mention the FastAPI migration work.",
                "bid_amount": 1500,
                "delivery_days": 21,
            }
        },
    )

    project_id: str = Field(
        min_length=1,
        max_length=100,
        description="ObjectId of an open project.",
    )
    freelancer_id: Optional[str] = Field(
        default=None,
        min_length=1,
        max_length=100,
        description=(
            "Optional compatibility field. When supplied it must match the "
            "authenticated freelancer."
        ),
    )
    tone: Tone = Field(
        default="Professional",
        description="Requested writing tone.",
    )
    length: Length = Field(
        default="medium",
        description="Requested proposal length.",
    )
    highlights: Optional[str] = Field(
        default=None,
        max_length=1500,
        description="Optional points the freelancer wants emphasised.",
    )
    bid_amount: Optional[float] = Field(
        default=None,
        ge=1,
        allow_inf_nan=False,
        description="Optional proposed budget.",
    )
    delivery_days: Optional[int] = Field(
        default=None,
        ge=1,
        le=730,
        description="Optional delivery estimate in days.",
    )

    @field_validator("highlights")
    @classmethod
    def empty_highlights_to_none(cls, value: Optional[str]) -> Optional[str]:
        return value or None


class SummaryRequest(BaseModel):
    """Payload accepted by ``POST /ai/generate-summary``.

    ``headline``, ``years_experience`` and ``skills`` are accepted because the
    existing frontend sends them, but the stored MongoDB profile remains the
    source of truth. They are validated for size and then ignored by the
    service.
    """

    model_config = ConfigDict(
        extra="ignore",
        str_strip_whitespace=True,
        json_schema_extra={
            "example": {
                "freelancer_id": "66f1a2b3c4d5e6f7a8b9c0d4",
                "headline": "Full-stack developer",
                "years_experience": 3,
                "skills": ["Python", "FastAPI", "MongoDB"],
                "highlights": "Delivered two production APIs.",
                "tone": "Professional",
                "length": "medium",
                "audience": "clients",
            }
        },
    )

    freelancer_id: Optional[str] = Field(
        default=None,
        min_length=1,
        max_length=100,
        description=(
            "Optional compatibility field. When supplied it must match the "
            "authenticated freelancer."
        ),
    )
    headline: Optional[str] = Field(
        default=None,
        max_length=100,
        description="Compatibility field; stored profile data is used instead.",
    )
    years_experience: Optional[int] = Field(
        default=None,
        ge=0,
        le=60,
        description="Compatibility field; stored profile data is used instead.",
    )
    skills: Optional[list[str]] = Field(
        default=None,
        max_length=25,
        description="Compatibility field; stored profile data is used instead.",
    )
    highlights: Optional[str] = Field(
        default=None,
        max_length=1500,
        description="Optional achievements the freelancer wants emphasised.",
    )
    tone: Tone = Field(
        default="Professional",
        description="Requested writing tone.",
    )
    length: Length = Field(
        default="medium",
        description="Requested summary length.",
    )
    audience: Literal["clients", "recruiters"] = Field(
        default="clients",
        description="Who will read the summary.",
    )

    @field_validator("highlights")
    @classmethod
    def empty_highlights_to_none(cls, value: Optional[str]) -> Optional[str]:
        return value or None

    @field_validator("skills")
    @classmethod
    def validate_skills(cls, value: Optional[list[str]]) -> Optional[list[str]]:
        if value is None:
            return None
        return clean_string_list(value, max_items=25, max_length=50)


class ProposalResponse(BaseModel):
    """Editable proposal text returned to the browser."""

    proposal: str = Field(description="Editable proposal draft.")


class SummaryResponse(BaseModel):
    """Editable profile summary text returned to the browser."""

    summary: str = Field(description="Editable profile summary draft.")
