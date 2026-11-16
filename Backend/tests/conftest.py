"""Shared pytest fixtures.

Tests never touch the real MongoDB Atlas cluster. The health endpoint is
tested with a fake ping so the suite is fast and deterministic. The real
connection is verified separately with:

    python -m Backend.scripts.check_db
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

# Set safe dummy values BEFORE importing the application. `load_dotenv` uses
# override=False, so these win over the real .env during tests.
os.environ.setdefault("MONGODB_URI", "mongodb://127.0.0.1:27017")
os.environ.setdefault("MONGO_DB_NAME", "freelancer_platform")
os.environ.setdefault("JWT_SECRET", "test-only-secret-not-for-production")

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import mongomock  # noqa: E402
import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from Backend.main import create_app  # noqa: E402


@pytest.fixture
def client(monkeypatch):
    """TestClient with a healthy fake database and no real I/O."""

    def fake_ping():
        return {
            "connected": True,
            "database": "freelancer_platform",
            "latency_ms": 1.23,
        }

    monkeypatch.setattr("Backend.main.ping_database", fake_ping)
    monkeypatch.setattr("Backend.main.ensure_indexes", lambda: None)
    monkeypatch.setattr("Backend.main.close_database", lambda: None)

    with TestClient(create_app()) as test_client:
        yield test_client


@pytest.fixture
def domain_db(monkeypatch):
    """One in-memory database shared by auth, freelancer, and project services.

    Phase 3 tests use this instead of the real Atlas cluster. The modules are
    patched by name because each service imports ``get_database`` itself.
    """
    db = mongomock.MongoClient().freelancer_platform
    db.users.create_index("email", unique=True)
    db.applications.create_index(
        [("project_id", 1), ("freelancer_id", 1)], unique=True
    )
    monkeypatch.setattr("Backend.services.auth_service.get_database", lambda: db)
    monkeypatch.setattr(
        "Backend.services.freelancer_service.get_database", lambda: db
    )
    monkeypatch.setattr(
        "Backend.services.project_service.get_database", lambda: db
    )
    monkeypatch.setattr(
        "Backend.services.application_service.get_database", lambda: db
    )
    monkeypatch.setattr("Backend.services.ml_service.get_database", lambda: db)
    return db
