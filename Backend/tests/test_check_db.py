"""Tests for the standalone MongoDB Atlas health-check script."""

from __future__ import annotations

import json
from types import SimpleNamespace

from Backend import db_diagnostics as diagnostics
from Backend.scripts import check_db


def _settings() -> SimpleNamespace:
    return SimpleNamespace(
        mongodb_uri=(
            "mongodb://alice:s3cret@127.0.0.1:27017/craftline"
        ),
        database_name="craftline",
    )


def _failed_ping() -> dict:
    return {
        "connected": False,
        "database": "craftline",
        "latency_ms": 12.5,
        "error": "ServerSelectionTimeoutError",
        "error_category": diagnostics.TLS_HANDSHAKE_REJECTED,
        "hint": "Atlas rejected the TLS handshake.",
    }


def test_check_db_json_is_safe_and_actionable(monkeypatch, capsys):
    monkeypatch.setattr(check_db, "get_settings", _settings)
    monkeypatch.setattr(check_db, "ping_database", _failed_ping)
    monkeypatch.setattr(check_db, "get_public_ip", lambda: "203.0.113.10")
    monkeypatch.setattr(check_db, "close_database", lambda: None)

    exit_code = check_db.main(["--json"])
    output = capsys.readouterr().out
    payload = json.loads(output)

    assert exit_code == 1
    assert payload["connected"] is False
    assert payload["error_category"] == diagnostics.TLS_HANDSHAKE_REJECTED
    assert payload["public_ip"] == "203.0.113.10"
    assert payload["likely_causes"]
    assert payload["next_steps"]
    assert "alice" not in output
    assert "s3cret" not in output


def test_check_db_human_output_mentions_network_access(monkeypatch, capsys):
    monkeypatch.setattr(check_db, "get_settings", _settings)
    monkeypatch.setattr(check_db, "ping_database", _failed_ping)
    monkeypatch.setattr(check_db, "get_public_ip", lambda: "203.0.113.10")
    monkeypatch.setattr(check_db, "close_database", lambda: None)

    exit_code = check_db.main([])
    output = capsys.readouterr().out

    assert exit_code == 1
    assert "FAILED: could not reach MongoDB Atlas." in output
    assert "tls_handshake_rejected" in output
    assert "Current public IP: 203.0.113.10" in output
    assert "Network Access" in output
    assert "alice" not in output
    assert "s3cret" not in output


def test_check_db_success_exit_zero(monkeypatch, capsys):
    monkeypatch.setattr(check_db, "get_settings", _settings)
    monkeypatch.setattr(
        check_db,
        "ping_database",
        lambda: {
            "connected": True,
            "database": "craftline",
            "latency_ms": 4.2,
        },
    )
    monkeypatch.setattr(
        check_db,
        "get_public_ip",
        lambda: (_ for _ in ()).throw(
            AssertionError("public IP lookup must not run on success")
        ),
    )
    monkeypatch.setattr(check_db, "close_database", lambda: None)

    exit_code = check_db.main([])
    output = capsys.readouterr().out

    assert exit_code == 0
    assert "OK: connected in 4.2 ms." in output
    assert "Database: craftline" in output


def test_check_db_probe_tls_is_opt_in(monkeypatch, capsys):
    called = {"probe": False}

    def fake_probe(uri: str):
        called["probe"] = True
        return [{"shard": 0, "ok": False, "error_category": "tls_handshake_rejected"}]

    monkeypatch.setattr(check_db, "get_settings", _settings)
    monkeypatch.setattr(check_db, "ping_database", _failed_ping)
    monkeypatch.setattr(check_db, "get_public_ip", lambda: "203.0.113.10")
    monkeypatch.setattr(check_db, "close_database", lambda: None)
    monkeypatch.setattr(check_db, "probe_tls_hosts", fake_probe)

    check_db.main(["--json"])
    capsys.readouterr()
    assert called["probe"] is False

    check_db.main(["--json", "--probe-tls"])
    capsys.readouterr()
    assert called["probe"] is True
