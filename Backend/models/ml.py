"""Phase 5 ML matching request and response schemas.

The browser sends only two identifiers. It can never submit feature values or
class probabilities that would be treated as model output.
"""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from Backend.models.freelancer import FreelancerPublic


class MatchRequest(BaseModel):
    """Payload for ``POST /ml/predict-match``."""

    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "example": {
                "freelancer_id": "66f1a2b3c4d5e6f7a8b9c0d4",
                "project_id": "66f1a2b3c4d5e6f7a8b9c0d2",
            }
        },
    )

    freelancer_id: str = Field(
        min_length=1,
        max_length=100,
        description="ObjectId of an existing freelancer profile.",
    )
    project_id: str = Field(
        min_length=1,
        max_length=100,
        description="ObjectId of an existing project.",
    )


class MatchProbabilities(BaseModel):
    """Class probabilities returned by the Random Forest."""

    strong: float = Field(ge=0, le=1)
    moderate: float = Field(ge=0, le=1)
    low: float = Field(ge=0, le=1)


class MatchFeatures(BaseModel):
    """Feature values and human-readable evidence used for one prediction."""

    skills_match_percentage: float = Field(ge=0, le=100)
    required_technology_match: float = Field(ge=0, le=100)
    category_relevance: float = Field(ge=0, le=1)
    years_experience: int = Field(ge=0, le=60)
    experience_level_compatibility: float = Field(ge=0, le=1)
    avg_rating: float = Field(ge=0, le=5)
    portfolio_evidence: float = Field(ge=0, le=1)
    work_history_evidence: float = Field(ge=0, le=1)
    matched_skills: list[str] = Field(default_factory=list)
    missing_skills: list[str] = Field(default_factory=list)
    required_technologies: list[str] = Field(default_factory=list)
    matched_technologies: list[str] = Field(default_factory=list)
    missing_technologies: list[str] = Field(default_factory=list)
    required_technology_count: int = Field(ge=0)
    matched_technology_count: int = Field(ge=0)
    project_category: str = ""
    experience_level: str = Field(
        default="",
        description="Frontend-compatible alias for the freelancer's experience level.",
    )
    freelancer_experience_level: str = ""
    project_experience_level: Optional[str] = None


class MatchPrediction(BaseModel):
    """A single freelancer-project match prediction."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "freelancer_id": "66f1a2b3c4d5e6f7a8b9c0d4",
                "project_id": "66f1a2b3c4d5e6f7a8b9c0d2",
                "label": "Strong Match",
                "rubric_score": 95.6,
                "match_percentage": 91.42,
                "confidence": 0.9142,
                "probabilities": {
                    "strong": 0.9142,
                    "moderate": 0.0715,
                    "low": 0.0143,
                },
                "expected_match_score": 94.21,
                "model_version": "phase5-rf-v1",
                "features": {
                    "skills_match_percentage": 100.0,
                    "required_technology_match": 100.0,
                    "category_relevance": 1.0,
                    "years_experience": 6,
                    "experience_level_compatibility": 1.0,
                    "avg_rating": 4.8,
                    "portfolio_evidence": 1.0,
                    "work_history_evidence": 1.0,
                    "matched_skills": ["FastAPI", "MongoDB", "Python"],
                    "missing_skills": [],
                    "required_technologies": ["FastAPI", "MongoDB", "Python"],
                    "matched_technologies": ["FastAPI", "MongoDB", "Python"],
                    "missing_technologies": [],
                    "required_technology_count": 3,
                    "matched_technology_count": 3,
                    "project_category": "Backend & APIs",
                    "experience_level": "Expert",
                    "freelancer_experience_level": "Expert",
                    "project_experience_level": "Intermediate",
                },
            }
        }
    )

    freelancer_id: str
    project_id: str
    label: str
    rubric_score: float = Field(
        ge=0,
        le=100,
        description=(
            "`rubric_score`: deterministic 0-100 fit score from the transparent "
            "rubric applied to the extracted live features. This is not the "
            "model probability and may differ from the predicted label."
        ),
    )
    match_percentage: float = Field(
        ge=0,
        le=100,
        description=(
            "Deprecated compatibility field: predicted-class confidence "
            "expressed as 0-100 (confidence * 100). It is not a match-quality "
            "score; use rubric_score for fit and confidence for the "
            "predicted-class probability."
        ),
    )
    confidence: float = Field(
        ge=0,
        le=1,
        description="Probability of the predicted class.",
    )
    probabilities: MatchProbabilities
    expected_match_score: float = Field(
        ge=0,
        le=100,
        description=(
            "Internal probability-weighted ranking score using 100/70/30 "
            "anchors for Strong, Moderate and Low. Useful for ranking, not a "
            "calibrated probability."
        ),
    )
    model_version: str
    features: MatchFeatures


class RankedFreelancerMatch(BaseModel):
    """One item in the client-only ranked freelancer list."""

    freelancer: FreelancerPublic
    label: str
    rubric_score: float = Field(
        ge=0,
        le=100,
        description=(
            "`rubric_score`: deterministic 0-100 fit score from the transparent "
            "rubric applied to the extracted live features. This is not the "
            "model probability and may differ from the predicted label."
        ),
    )
    match_percentage: float = Field(
        ge=0,
        le=100,
        description=(
            "Deprecated compatibility field: predicted-class confidence "
            "expressed as 0-100 (confidence * 100). It is not a match-quality "
            "score; use rubric_score for fit and confidence for the "
            "predicted-class probability."
        ),
    )
    confidence: float = Field(
        ge=0,
        le=1,
        description="Probability of the predicted class.",
    )
    probabilities: MatchProbabilities
    expected_match_score: float = Field(
        ge=0,
        le=100,
        description=(
            "Internal probability-weighted ranking score using 100/70/30 "
            "anchors for Strong, Moderate and Low."
        ),
    )
    features: MatchFeatures


class RankedFreelancerListResponse(BaseModel):
    """Ranked freelancers for a client-owned project."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "project_id": "66f1a2b3c4d5e6f7a8b9c0d2",
                "items": [
                    {
                        "freelancer": {
                            "id": "66f1a2b3c4d5e6f7a8b9c0d4",
                            "name": "Aarav Sharma",
                            "headline": "Full-stack developer",
                            "summary": "I build secure FastAPI services.",
                            "location": "Pune, India",
                            "availability": "Available now",
                            "skills": ["Python", "FastAPI", "MongoDB"],
                            "years_experience": 6,
                            "experience_level": "Expert",
                            "hourly_rate": 35.0,
                            "currency": "USD",
                            "avg_rating": 4.8,
                            "reviews_count": 12,
                            "completed_projects": 9,
                            "avatar_url": None,
                            "portfolio": [],
                            "work_history": [],
                        },
                        "label": "Strong Match",
                        "rubric_score": 95.6,
                        "match_percentage": 91.42,
                        "confidence": 0.9142,
                        "probabilities": {
                            "strong": 0.9142,
                            "moderate": 0.0715,
                            "low": 0.0143,
                        },
                        "expected_match_score": 94.21,
                        "features": {
                            "skills_match_percentage": 100.0,
                            "required_technology_match": 100.0,
                            "category_relevance": 1.0,
                            "years_experience": 6,
                            "experience_level_compatibility": 1.0,
                            "avg_rating": 4.8,
                            "portfolio_evidence": 1.0,
                            "work_history_evidence": 1.0,
                            "matched_skills": ["FastAPI", "MongoDB", "Python"],
                            "missing_skills": [],
                            "required_technologies": [
                                "FastAPI",
                                "MongoDB",
                                "Python",
                            ],
                            "matched_technologies": [
                                "FastAPI",
                                "MongoDB",
                                "Python",
                            ],
                            "missing_technologies": [],
                            "required_technology_count": 3,
                            "matched_technology_count": 3,
                            "project_category": "Backend & APIs",
                            "experience_level": "Expert",
                            "freelancer_experience_level": "Expert",
                            "project_experience_level": "Intermediate",
                        },
                    }
                ],
                "total": 1,
                "model_version": "phase5-rf-v1",
            }
        }
    )

    project_id: str
    items: list[RankedFreelancerMatch]
    total: int = Field(
        ge=0,
        description="Number of candidate freelancer profiles scored before the limit.",
    )
    model_version: str
