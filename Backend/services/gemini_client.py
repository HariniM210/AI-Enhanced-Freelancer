"""Minimal, testable wrapper around the Google Gemini SDK.

Only this module touches the SDK. Prompts and API keys are never logged.
Provider error messages are bounded and have likely secrets redacted before
logging so failures remain diagnosable. Callers translate the typed exceptions
below into safe HTTP responses.
"""

from __future__ import annotations

import logging
import re
import threading
from typing import Optional

from google import genai
from google.genai import errors as genai_errors
from google.genai import types as genai_types

from Backend.config import get_settings

logger = logging.getLogger(__name__)


class GeminiClientError(Exception):
    """Base class for safe, typed Gemini failures."""


class GeminiConfigurationError(GeminiClientError):
    """The Gemini API key or client configuration is missing."""


class GeminiPermissionError(GeminiClientError):
    """Gemini rejected the API key or the project's API access (401/403)."""


class GeminiModelNotFoundError(GeminiClientError):
    """Gemini could not find the configured model or API endpoint (404)."""


class GeminiRateLimitError(GeminiClientError):
    """Gemini rejected the request because of rate limiting or quota."""


class GeminiTimeoutError(GeminiClientError):
    """The Gemini request exceeded the configured timeout."""


class GeminiUpstreamError(GeminiClientError):
    """Gemini returned an error or an unusable response."""


class GeminiEmptyResponseError(GeminiClientError):
    """Gemini returned no text."""


_client: Optional[genai.Client] = None
_client_lock = threading.Lock()


def reset_client() -> None:
    """Clear the cached client. Used by tests and configuration reloads."""
    global _client
    with _client_lock:
        _client = None


def _get_client() -> genai.Client:
    """Build the SDK client lazily so importing the app never needs a key."""
    settings = get_settings()
    if not settings.gemini_api_key:
        raise GeminiConfigurationError("Gemini API key is not configured.")

    global _client
    if _client is None:
        with _client_lock:
            if _client is None:
                _client = genai.Client(
                    api_key=settings.gemini_api_key,
                    http_options=genai_types.HttpOptions(
                        timeout=settings.gemini_timeout_ms
                    ),
                )
    return _client


_SECRET_PATTERNS = (
    re.compile(r"(?i)(x-goog-api-key\s*[:=]\s*)[^\s,;]+"),
    re.compile(r"(?i)(authorization\s*:\s*bearer\s+)[^\s,;]+"),
    re.compile(r"(?i)([?&](?:key|api_key|access_token)=)[^&\s]+"),
    re.compile(r"\bAQ\.[A-Za-z0-9._\-]{10,}\b"),
    re.compile(r"\bAIza[0-9A-Za-z._\-]{20,}\b"),
)


def _safe_provider_message(exc: Exception) -> str:
    """Return a bounded provider message with likely secrets redacted."""
    message = getattr(exc, "message", None)
    if not isinstance(message, str) or not message.strip():
        message = str(exc)
    message = " ".join(message.split())
    for pattern in _SECRET_PATTERNS:
        message = pattern.sub(
            lambda match: (
                match.group(1) + "[redacted]"
                if match.groups()
                else "[redacted]"
            ),
            message,
        )
    return message[:300] + ("..." if len(message) > 300 else "")


def _is_timeout(exc: Exception) -> bool:
    """Recognise timeout errors without importing a specific HTTP library."""
    name = type(exc).__name__.lower()
    return isinstance(exc, TimeoutError) or "timeout" in name


def generate_text(
    *,
    system_instruction: str,
    prompt: str,
    max_output_tokens: int,
    temperature: float = 0.4,
) -> str:
    """Generate text with Gemini and translate provider failures safely.

    The returned text is stripped but not otherwise rewritten; the AI service
    applies feature-specific cleaning and length limits.
    """
    settings = get_settings()
    client = _get_client()

    try:
        response = client.models.generate_content(
            model=settings.gemini_model,
            contents=prompt,
            config=genai_types.GenerateContentConfig(
                system_instruction=system_instruction,
                temperature=temperature,
                max_output_tokens=max_output_tokens,
            ),
        )
    except genai_errors.APIError as exc:
        code = int(getattr(exc, "code", 0) or 0)
        status_name = getattr(exc, "status", None)
        safe_message = _safe_provider_message(exc)
        if code == 404:
            logger.warning(
                "Gemini model/API endpoint not found (code=%s, status=%s): %s",
                code,
                status_name,
                safe_message,
            )
            raise GeminiModelNotFoundError(
                "Gemini model was not found."
            ) from exc
        if code == 429:
            logger.warning(
                "Gemini rate limit reached (code=%s, status=%s): %s",
                code,
                status_name,
                safe_message,
            )
            raise GeminiRateLimitError("Gemini rate limit reached.") from exc
        if code in (408, 504):
            logger.warning(
                "Gemini request timed out (code=%s, status=%s): %s",
                code,
                status_name,
                safe_message,
            )
            raise GeminiTimeoutError("Gemini request timed out.") from exc
        if code in (401, 403):
            logger.warning(
                "Gemini rejected credentials or project access "
                "(code=%s, status=%s): %s",
                code,
                status_name,
                safe_message,
            )
            raise GeminiPermissionError(
                "Gemini rejected the configured credentials or project access."
            ) from exc
        logger.warning(
            "Gemini API error (code=%s, status=%s): %s",
            code,
            status_name,
            safe_message,
        )
        raise GeminiUpstreamError("Gemini request failed.") from exc
    except Exception as exc:  # noqa: BLE001 - never leak provider details
        if _is_timeout(exc):
            logger.warning(
                "Gemini request timed out: %s", _safe_provider_message(exc)
            )
            raise GeminiTimeoutError("Gemini request timed out.") from exc
        logger.warning(
            "Gemini request failed (%s): %s",
            type(exc).__name__,
            _safe_provider_message(exc),
        )
        raise GeminiUpstreamError("Gemini request failed.") from exc

    try:
        text = response.text
    except Exception as exc:  # noqa: BLE001 - response shape is provider-owned
        logger.warning(
            "Gemini response could not be read (%s).", type(exc).__name__
        )
        raise GeminiEmptyResponseError("Gemini returned no text.") from exc

    if not isinstance(text, str) or not text.strip():
        raise GeminiEmptyResponseError("Gemini returned no text.")
    return text.strip()
