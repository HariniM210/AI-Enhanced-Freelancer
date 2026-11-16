"""Tests for safe MongoDB Atlas connection diagnostics."""

from __future__ import annotations

import json
import ssl
from types import SimpleNamespace

from pymongo.errors import OperationFailure, ServerSelectionTimeoutError

from Backend import db_diagnostics as diagnostics
from Backend.database import ping_database


def _tls_alert_error() -> ServerSelectionTimeoutError:
    return ServerSelectionTimeoutError(
        "SSL handshake failed: [SSL: TLSV1_ALERT_INTERNAL_ERROR] "
        "tlsv1 alert internal error (SSL alert number 80)"
    )


def test_classifies_atlas_tls_alert_80():
    assert (
        diagnostics.classify_exception(_tls_alert_error())
        == diagnostics.TLS_HANDSHAKE_REJECTED
    )


def test_classifies_nested_tls_alert_80():
    try:
        try:
            raise ssl.SSLError(
                "[SSL: TLSV1_ALERT_INTERNAL_ERROR] tlsv1 alert internal error"
            )
        except ssl.SSLError as inner:
            raise ServerSelectionTimeoutError("server selection timed out") from inner
    except ServerSelectionTimeoutError as exc:
        assert (
            diagnostics.classify_exception(exc)
            == diagnostics.TLS_HANDSHAKE_REJECTED
        )


def test_classifies_certificate_verification_failure():
    exc = ssl.SSLError(
        "[SSL: CERTIFICATE_VERIFY_FAILED] certificate verify failed: "
        "unable to get local issuer certificate"
    )
    assert (
        diagnostics.classify_exception(exc)
        == diagnostics.TLS_CERTIFICATE_ERROR
    )


def test_classifies_dns_srv_timeout():
    exc = ServerSelectionTimeoutError(
        "querySrv ETIMEOUT _mongodb._tcp.cluster.example"
    )
    assert diagnostics.classify_exception(exc) == diagnostics.DNS_ERROR


def test_classifies_authentication_failure():
    exc = OperationFailure("Authentication failed.")
    assert (
        diagnostics.classify_exception(exc)
        == diagnostics.AUTHENTICATION_ERROR
    )


def test_classifies_connection_refused():
    exc = ConnectionRefusedError(10061, "Connection refused")
    assert (
        diagnostics.classify_exception(exc)
        == diagnostics.CONNECTION_REFUSED
    )


def test_classifies_timeout():
    exc = ServerSelectionTimeoutError("No servers found yet")
    assert diagnostics.classify_exception(exc) == diagnostics.TIMEOUT


def test_classifies_unknown_error():
    assert (
        diagnostics.classify_exception(ValueError("boom"))
        == diagnostics.UNKNOWN_ERROR
    )


def test_tls_failure_details_are_actionable_and_safe():
    details = diagnostics.failure_details(
        diagnostics.TLS_HANDSHAKE_REJECTED
    )
    assert "Network Access" in " ".join(details["next_steps"])
    assert "TLS" in details["summary"]
    assert not any("mongodb://" in item for item in details["next_steps"])


def test_describe_uri_never_exposes_credentials():
    described = diagnostics.describe_uri(
        "mongodb://alice:s3cret@127.0.0.1:27017/craftline"
        "?authSource=admin&retryWrites=true&w=majority"
    )
    rendered = json.dumps(described)

    assert "alice" not in rendered
    assert "s3cret" not in rendered
    assert described["scheme"] == "mongodb"
    assert described["host_count"] == 1
    assert described["database"] == "craftline"
    assert described["username_present"] is True
    assert described["password_present"] is True
    assert described["auth_source"] == "admin"
    assert described["tls"] is False
    assert described["tls_insecure"] is False


def test_describe_uri_flags_insecure_tls_options():
    described = diagnostics.describe_uri(
        "mongodb://127.0.0.1:27017/craftline"
        "?tls=true&tlsAllowInvalidCertificates=true"
    )
    assert described["tls"] is True
    assert described["tls_insecure"] is True


def test_describe_uri_defaults_to_tls_for_srv(monkeypatch):
    monkeypatch.setattr(
        diagnostics,
        "parse_uri",
        lambda uri: {
            "nodelist": [("example.invalid", 27017)],
            "options": {},
            "database": None,
            "username": None,
            "password": None,
        },
    )
    described = diagnostics.describe_uri("mongodb+srv://example.invalid")
    assert described["scheme"] == "mongodb+srv"
    assert described["tls"] is True


def test_ping_database_returns_safe_tls_category(monkeypatch):
    raw_message = (
        "SSL handshake failed: [SSL: TLSV1_ALERT_INTERNAL_ERROR] "
        "secret-host.example.net"
    )

    def fail_client():
        raise ServerSelectionTimeoutError(raw_message)

    monkeypatch.setattr("Backend.database.get_client", fail_client)

    result = ping_database()

    assert result["connected"] is False
    assert result["error"] == "ServerSelectionTimeoutError"
    assert result["error_category"] == diagnostics.TLS_HANDSHAKE_REJECTED
    assert "Atlas rejected the TLS handshake" in result["hint"]
    assert "secret-host.example.net" not in json.dumps(result)


def test_build_report_includes_safe_guidance():
    settings = SimpleNamespace(
        mongodb_uri="mongodb://alice:s3cret@127.0.0.1:27017/craftline",
        database_name="craftline",
    )
    ping_result = {
        "connected": False,
        "database": "craftline",
        "latency_ms": 1.0,
        "error": "ServerSelectionTimeoutError",
        "error_category": diagnostics.TLS_HANDSHAKE_REJECTED,
        "hint": "Atlas rejected the TLS handshake.",
    }

    report = diagnostics.build_report(
        ping_result,
        settings,
        public_ip="203.0.113.10",
        include_environment=True,
    )

    assert report["public_ip"] == "203.0.113.10"
    assert report["error_category"] == diagnostics.TLS_HANDSHAKE_REJECTED
    assert report["likely_causes"]
    assert report["next_steps"]
    assert "python" in report["environment"]
    assert "openssl" in report["environment"]
    rendered = json.dumps(report)
    assert "alice" not in rendered
    assert "s3cret" not in rendered


def test_get_public_ip_accepts_valid_address(monkeypatch):
    class FakeResponse:
        def __init__(self, body: bytes) -> None:
            self._body = body

        def read(self, _size: int) -> bytes:
            return self._body

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    monkeypatch.setattr(
        diagnostics.urllib.request,
        "urlopen",
        lambda *args, **kwargs: FakeResponse(b"203.0.113.10"),
    )
    assert diagnostics.get_public_ip() == "203.0.113.10"


def test_get_public_ip_rejects_non_ip(monkeypatch):
    class FakeResponse:
        def read(self, _size: int) -> bytes:
            return b"not-an-ip"

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    monkeypatch.setattr(
        diagnostics.urllib.request,
        "urlopen",
        lambda *args, **kwargs: FakeResponse(),
    )
    assert diagnostics.get_public_ip() is None


def test_probe_tls_reports_rejected_handshake(monkeypatch):
    def fail_connection(*args, **kwargs):
        raise ssl.SSLError(
            "[SSL: TLSV1_ALERT_INTERNAL_ERROR] tlsv1 alert internal error"
        )

    monkeypatch.setattr(
        diagnostics.socket, "create_connection", fail_connection
    )

    result = diagnostics.probe_tls("example.invalid")

    assert result["ok"] is False
    assert result["error_category"] == diagnostics.TLS_HANDSHAKE_REJECTED
    assert "example.invalid" not in json.dumps(result)


def test_probe_tls_reports_success(monkeypatch):
    class FakeTLS:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def version(self):
            return "TLSv1.3"

        def cipher(self):
            return ("TLS_AES_256_GCM_SHA384", "TLSv1.3", 256)

    class FakeContext:
        def wrap_socket(self, raw, server_hostname=None):
            return FakeTLS()

    class FakeRaw:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    monkeypatch.setattr(
        diagnostics.socket,
        "create_connection",
        lambda *args, **kwargs: FakeRaw(),
    )
    monkeypatch.setattr(
        diagnostics.ssl,
        "create_default_context",
        lambda: FakeContext(),
    )

    result = diagnostics.probe_tls("example.invalid")

    assert result["ok"] is True
    assert result["tls_version"] == "TLSv1.3"
    assert result["cipher"] == "TLS_AES_256_GCM_SHA384"
