"""Phase 6 Gemini-backed proposal and profile-summary routes.

Both endpoints require a freelancer JWT. The server loads the profile and
project facts itself; the browser never supplies authoritative profile data.
Neither endpoint writes to the database.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from Backend.dependencies import require_role
from Backend.models.ai import (
    ProposalRequest,
    ProposalResponse,
    SummaryRequest,
    SummaryResponse,
)
from Backend.services.ai_service import (
    AIIdentityError,
    AIOutputError,
    AIServiceError,
    ProfileNotFoundError,
    ProjectNotFoundError,
    ProjectNotOpenError,
    generate_proposal,
    generate_summary,
)
from Backend.services.gemini_client import (
    GeminiClientError,
    GeminiConfigurationError,
    GeminiEmptyResponseError,
    GeminiModelNotFoundError,
    GeminiPermissionError,
    GeminiRateLimitError,
    GeminiTimeoutError,
    GeminiUpstreamError,
)

router = APIRouter(prefix="/ai", tags=["ai"])

AI_CONFIGURATION_DETAIL = (
    "AI service is not configured. Add GEMINI_API_KEY to the backend .env."
)
AI_PERMISSION_DETAIL = (
    "The AI service rejected the configured credentials or project access. "
    "Check the Gemini API key and the project's billing/API access."
)
AI_MODEL_DETAIL = (
    "The configured AI model is unavailable. Update GEMINI_MODEL to a "
    "supported Gemini model."
)
AI_RATE_LIMIT_DETAIL = (
    "The AI service is rate-limited. Please try again shortly."
)
AI_UPSTREAM_DETAIL = (
    "The AI service could not generate a response. Please try again."
)
AI_TIMEOUT_DETAIL = "The AI service timed out. Please try again."


def _translate_ai_error(exc: Exception) -> HTTPException:
    """Map typed service failures to safe HTTP responses."""
    if isinstance(exc, AIIdentityError):
        return HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)
        )
    if isinstance(exc, (ProfileNotFoundError, ProjectNotFoundError)):
        return HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
        )
    if isinstance(exc, ProjectNotOpenError):
        return HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(exc)
        )
    if isinstance(exc, GeminiConfigurationError):
        return HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=AI_CONFIGURATION_DETAIL,
        )
    if isinstance(exc, GeminiPermissionError):
        return HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=AI_PERMISSION_DETAIL,
        )
    if isinstance(exc, GeminiModelNotFoundError):
        return HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=AI_MODEL_DETAIL,
        )
    if isinstance(exc, GeminiRateLimitError):
        return HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=AI_RATE_LIMIT_DETAIL,
        )
    if isinstance(exc, GeminiTimeoutError):
        return HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail=AI_TIMEOUT_DETAIL,
        )
    if isinstance(
        exc, (GeminiUpstreamError, GeminiEmptyResponseError, AIOutputError)
    ):
        return HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=AI_UPSTREAM_DETAIL,
        )
    return HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="Internal server error.",
    )


@router.post(
    "/generate-proposal",
    response_model=ProposalResponse,
    summary="Generate an editable project proposal",
    description=(
        "Load the authenticated freelancer's stored profile and the requested "
        "open project, then generate an editable proposal. The browser sends "
        "only ids and writing preferences. This endpoint never creates an "
        "application or submits a proposal."
    ),
    responses={
        401: {"description": "Authentication required."},
        403: {"description": "Freelancer role or matching identity required."},
        404: {"description": "Freelancer profile or project not found."},
        409: {"description": "The project is not open."},
        429: {"description": "Gemini rate limit reached."},
        502: {"description": "Gemini returned an unusable response."},
        503: {
            "description": (
                "Gemini is not configured, the model is unavailable, or "
                "access was rejected."
            )
        },
        504: {"description": "Gemini timed out."},
    },
)
def generate_proposal_route(
    payload: ProposalRequest,
    current_user: dict = Depends(require_role("freelancer")),
) -> dict:
    try:
        proposal = generate_proposal(payload, current_user)
    except (AIServiceError, GeminiClientError) as exc:
        raise _translate_ai_error(exc) from exc
    return {"proposal": proposal}


@router.post(
    "/generate-summary",
    response_model=SummaryResponse,
    summary="Generate an editable freelancer profile summary",
    description=(
        "Use the authenticated freelancer's stored MongoDB profile as the "
        "source of truth and generate an editable summary. The endpoint never "
        "updates the profile; saving remains an explicit frontend action."
    ),
    responses={
        401: {"description": "Authentication required."},
        403: {"description": "Freelancer role or matching identity required."},
        404: {"description": "Freelancer profile not found."},
        429: {"description": "Gemini rate limit reached."},
        502: {"description": "Gemini returned an unusable response."},
        503: {
            "description": (
                "Gemini is not configured, the model is unavailable, or "
                "access was rejected."
            )
        },
        504: {"description": "Gemini timed out."},
    },
)
def generate_summary_route(
    payload: SummaryRequest,
    current_user: dict = Depends(require_role("freelancer")),
) -> dict:
    try:
        summary = generate_summary(payload, current_user)
    except (AIServiceError, GeminiClientError) as exc:
        raise _translate_ai_error(exc) from exc
    return {"summary": summary}
