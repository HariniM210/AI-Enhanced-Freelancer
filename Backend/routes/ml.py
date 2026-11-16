"""Phase 5 ML matching routes.

``POST /ml/predict-match`` matches the existing Frontend(2) contract. The
client-only ranking endpoint adds a safe way for a project owner to compare
public freelancer profiles without exposing private account fields.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status

from Backend.dependencies import get_current_user, require_role
from Backend.models.ml import (
    MatchPrediction,
    MatchRequest,
    RankedFreelancerListResponse,
)
from Backend.services.ml_service import (
    FreelancerNotFoundError,
    ModelUnavailableError,
    ProjectAccessDeniedError,
    ProjectNotFoundError,
    predict_match,
    rank_freelancers_for_project,
)

router = APIRouter(prefix="/ml", tags=["ml"])

MODEL_UNAVAILABLE_DETAIL = (
    "Match model is unavailable. Train it with python -m ML.scripts.train_model."
)


@router.post(
    "/predict-match",
    response_model=MatchPrediction,
    summary="Predict freelancer-project match",
    description=(
        "Run the Phase 5 Random Forest on public freelancer and project data. "
        "Returns the predicted three-class label, a deterministic rubric fit "
        "score computed from the live features, class probabilities, a clearly "
        "labelled predicted-class confidence, and the extracted "
        "skills/experience evidence. The legacy match_percentage field is "
        "deprecated: it is only confidence * 100, not a match-quality score. "
        "The browser supplies only ids; feature values, probabilities and "
        "rubric scores are always computed by the server."
    ),
    responses={
        401: {"description": "Authentication required."},
        404: {"description": "Freelancer profile or project not found."},
        503: {"description": "The trained model is unavailable."},
    },
)
def predict_match_route(
    payload: MatchRequest,
    current_user: dict = Depends(get_current_user),
) -> dict:
    try:
        return predict_match(payload.freelancer_id, payload.project_id)
    except (FreelancerNotFoundError, ProjectNotFoundError) as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except ModelUnavailableError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=MODEL_UNAVAILABLE_DETAIL,
        ) from exc


@router.get(
    "/projects/{project_id}/matches",
    response_model=RankedFreelancerListResponse,
    summary="Rank freelancers for a client-owned project",
    description=(
        "Score public freelancer profiles against one project and return the "
        "top matches. Only the client who owns the project may call this "
        "endpoint. Private account fields such as email, password hashes and "
        "user ids are never returned. Each item includes the predicted label, "
        "rubric fit score, predicted-class confidence and probabilities. "
        "Ranking still uses expected_match_score internally. The deprecated "
        "match_percentage field is retained only for older clients."
    ),
    responses={
        401: {"description": "Authentication required."},
        403: {"description": "Only the owning client may rank freelancers."},
        404: {"description": "Project not found."},
        503: {"description": "The trained model is unavailable."},
    },
)
def rank_freelancers_route(
    project_id: str,
    limit: int = Query(10, ge=1, le=50),
    current_user: dict = Depends(require_role("client")),
) -> dict:
    try:
        return rank_freelancers_for_project(
            project_id,
            current_user,
            limit=limit,
        )
    except ProjectNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except ProjectAccessDeniedError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(exc),
        ) from exc
    except ModelUnavailableError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=MODEL_UNAVAILABLE_DETAIL,
        ) from exc
