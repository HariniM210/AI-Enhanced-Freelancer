"""Configuration and secret-hygiene tests."""

from __future__ import annotations

import pytest

from Backend.config import ENV_FILE, PROJECT_ROOT, get_settings


def test_database_name_is_freelancer_platform():
    settings = get_settings()
    assert settings.database_name == "freelancer_platform"


def test_mongodb_uri_has_expected_scheme():
    settings = get_settings()
    assert settings.mongodb_uri.startswith(("mongodb://", "mongodb+srv://"))


def test_settings_repr_hides_secrets():
    """Printing settings must not reveal the URI or secrets."""
    settings = get_settings()
    rendered = repr(settings)
    assert settings.mongodb_uri not in rendered
    assert "mongodb://" not in rendered
    assert "mongodb+srv://" not in rendered


def test_env_example_contains_placeholders_only():
    path = PROJECT_ROOT / ".env.example"
    assert path.exists()
    text = path.read_text(encoding="utf-8")

    assert "MONGODB_URI=" in text
    assert "<username>" in text
    assert "<password>" in text
    assert "MONGO_DB_NAME=freelancer_platform" in text
    assert "JWT_SECRET=" in text
    assert "GEMINI_API_KEY=" in text
    assert "GEMINI_MODEL=gemini-3.5-flash-lite" in text
    assert "GEMINI_TIMEOUT_MS=60000" in text
    assert "CORS_ORIGINS=" in text


def test_gemini_settings_are_safe():
    settings = get_settings()
    assert settings.gemini_model
    assert settings.gemini_timeout_ms > 0
    if settings.gemini_api_key:
        assert settings.gemini_api_key not in repr(settings)


def test_gitignore_excludes_env_file():
    path = PROJECT_ROOT / ".gitignore"
    assert path.exists()
    lines = {line.strip() for line in path.read_text(encoding="utf-8").splitlines()}
    assert ".env" in lines
    assert ".env.*" in lines
    assert "!.env.example" in lines


def test_root_env_file_exists_and_declares_mongodb_uri():
    """The real .env must exist and declare the key. Its value is never read here."""
    if not ENV_FILE.exists():
        pytest.skip("Root .env is not present in this environment.")

    keys = set()
    for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        keys.add(stripped.split("=", 1)[0].strip())

    assert "MONGODB_URI" in keys
