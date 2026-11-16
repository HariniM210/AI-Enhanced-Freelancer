"""Application configuration loaded from environment variables.

All secrets are read from the project-root ``.env`` file (or the process
environment). They are never printed, logged, or hardcoded here.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import List

from dotenv import load_dotenv

# The .env file lives at the repository root, one level above Backend/.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
ENV_FILE = PROJECT_ROOT / ".env"

# Load .env once at import time. Existing environment variables win, which is
# what deployments and tests expect. Missing file is not an error.
load_dotenv(dotenv_path=ENV_FILE, override=False)


def _get_str(name: str, default: str | None = None, required: bool = False) -> str | None:
    """Read a trimmed string from the environment."""
    value = os.getenv(name)
    if value is None or not value.strip():
        if required:
            raise RuntimeError(
                f"Missing required environment variable '{name}'. "
                f"Add it to {ENV_FILE} (see .env.example)."
            )
        return default
    return value.strip()


def _get_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    try:
        return int(raw.strip())
    except ValueError as exc:
        raise RuntimeError(f"Environment variable '{name}' must be an integer.") from exc


def _get_positive_int(name: str, default: int) -> int:
    value = _get_int(name, default)
    if value <= 0:
        raise RuntimeError(
            f"Environment variable '{name}' must be greater than zero."
        )
    return value


def _get_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _get_list(name: str, default: List[str]) -> List[str]:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return list(default)
    return [item.strip() for item in raw.split(",") if item.strip()]


@dataclass(frozen=True)
class Settings:
    """Typed application settings.

    Fields holding credentials use ``repr=False`` so an accidental
    ``print(settings)`` cannot expose them.
    """

    app_name: str
    app_version: str
    debug: bool
    mongodb_uri: str = field(repr=False)
    database_name: str
    mongodb_timeout_ms: int
    cors_origins: List[str]
    jwt_secret: str | None = field(default=None, repr=False)
    jwt_expire_minutes: int = 1440
    gemini_api_key: str | None = field(default=None, repr=False)
    gemini_model: str = "gemini-3.5-flash-lite"
    gemini_timeout_ms: int = 60000

    @property
    def env_file(self) -> Path:
        return ENV_FILE


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Build and cache the settings object for the lifetime of the process."""
    mongodb_uri = _get_str("MONGODB_URI", required=True)
    if not mongodb_uri.startswith(("mongodb://", "mongodb+srv://")):
        raise RuntimeError(
            "MONGODB_URI must start with 'mongodb://' or 'mongodb+srv://'. "
            f"Check {ENV_FILE}."
        )

    return Settings(
        app_name=_get_str("APP_NAME", "CraftLine AI") or "CraftLine AI",
        app_version=_get_str("APP_VERSION", "1.0.0") or "1.0.0",
        debug=_get_bool("DEBUG", False),
        mongodb_uri=mongodb_uri,
        # The academic project uses this database name. Override with
        # MONGO_DB_NAME in .env if you ever need a separate environment.
        database_name=_get_str("MONGO_DB_NAME", "freelancer_platform") or "freelancer_platform",
        mongodb_timeout_ms=_get_int("MONGODB_TIMEOUT_MS", 5000),
        cors_origins=_get_list(
            "CORS_ORIGINS",
            ["http://127.0.0.1:5500", "http://localhost:5500"],
        ),
        jwt_secret=_get_str("JWT_SECRET"),
        jwt_expire_minutes=_get_int("JWT_EXPIRE_MINUTES", 1440),
        gemini_api_key=_get_str("GEMINI_API_KEY"),
        gemini_model=_get_str("GEMINI_MODEL", "gemini-3.5-flash-lite") or "gemini-3.5-flash-lite",
        gemini_timeout_ms=_get_positive_int("GEMINI_TIMEOUT_MS", 60000),
    )
