"""Health and CORS tests (no real database required)."""

from __future__ import annotations

from fastapi.testclient import TestClient

from Backend.main import create_app


def test_root_returns_service_metadata(client):
    response = client.get("/")
    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "CraftLine AI"
    assert body["docs"] == "/docs"
    assert body["health"] == "/health"


def test_health_ok(client):
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["database"]["status"] == "connected"
    assert body["database"]["name"] == "freelancer_platform"
    assert body["database"]["latency_ms"] >= 0
    assert "timestamp" in body


def test_health_db_ok(client):
    response = client.get("/health/db")
    assert response.status_code == 200
    body = response.json()
    assert body["connected"] is True
    assert body["database"] == "freelancer_platform"


def test_health_reports_degraded_when_database_is_down(monkeypatch):
    monkeypatch.setattr(
        "Backend.main.ping_database",
        lambda: {
            "connected": False,
            "database": "freelancer_platform",
            "latency_ms": 5.0,
            "error": "ServerSelectionTimeoutError",
            "error_category": "tls_handshake_rejected",
            "hint": "Atlas rejected the TLS handshake.",
        },
    )
    monkeypatch.setattr("Backend.main.ensure_indexes", lambda: None)
    monkeypatch.setattr("Backend.main.close_database", lambda: None)

    with TestClient(create_app()) as client:
        response = client.get("/health")
        assert response.status_code == 503
        body = response.json()
        assert body["status"] == "degraded"
        assert body["database"]["status"] == "unavailable"
        assert body["database"]["error_category"] == "tls_handshake_rejected"
        assert "Atlas rejected" in body["database"]["hint"]


def test_health_db_reports_safe_diagnostic_category(monkeypatch):
    monkeypatch.setattr(
        "Backend.main.ping_database",
        lambda: {
            "connected": False,
            "database": "freelancer_platform",
            "latency_ms": 5.0,
            "error": "ServerSelectionTimeoutError",
            "error_category": "tls_handshake_rejected",
            "hint": "Atlas rejected the TLS handshake.",
        },
    )
    monkeypatch.setattr("Backend.main.ensure_indexes", lambda: None)
    monkeypatch.setattr("Backend.main.close_database", lambda: None)

    with TestClient(create_app()) as client:
        response = client.get("/health/db")
        assert response.status_code == 503
        body = response.json()
        assert body["connected"] is False
        assert body["error_category"] == "tls_handshake_rejected"
        assert body["hint"]
        assert "mongodb://" not in response.text
        assert "mongodb+srv://" not in response.text


def test_cors_allows_frontend_origin(client):
    response = client.options(
        "/health",
        headers={
            "Origin": "http://127.0.0.1:5500",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://127.0.0.1:5500"


def test_unknown_route_returns_404(client):
    response = client.get("/does-not-exist")
    assert response.status_code == 404
