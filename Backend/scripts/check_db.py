"""Sanitized MongoDB Atlas connectivity check.

Run from the project root:

    python -m Backend.scripts.check_db
    python -m Backend.scripts.check_db --verbose
    python -m Backend.scripts.check_db --probe-tls
    python -m Backend.scripts.check_db --json

This script never prints the connection string, username, password, or
cluster hostnames. It classifies TLS, DNS, authentication, and timeout
failures so the next action is clear.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Sequence

# Allow `python Backend/scripts/check_db.py` as well as `python -m ...`.
PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from Backend.config import get_settings  # noqa: E402
from Backend.database import close_database, ping_database  # noqa: E402
from Backend.db_diagnostics import (  # noqa: E402
    build_report,
    get_public_ip,
    probe_tls_hosts,
)


def _print_human(report: dict[str, Any]) -> None:
    if report.get("connected"):
        print(f"OK: connected in {report['latency_ms']} ms.")
        print(f"Database: {report['database']}")
        return

    print("FAILED: could not reach MongoDB Atlas.")
    print(
        f"Reason: {report.get('error', 'unknown error')} "
        f"({report.get('error_category', 'unknown_error')})"
    )
    print(
        "What this means: "
        f"{report.get('hint', 'The database is unavailable.')}"
    )

    if report.get("public_ip"):
        print(f"Current public IP: {report['public_ip']}")
        print(f"Atlas Network Access entry: {report['public_ip']}/32")

    if report.get("likely_causes"):
        print("Likely causes:")
        for item in report["likely_causes"]:
            print(f"  - {item}")

    if report.get("next_steps"):
        print("Next steps:")
        for index, item in enumerate(report["next_steps"], 1):
            print(f"  {index}. {item}")

    uri = report.get("uri") or {}
    if uri:
        print("Connection settings:")
        print(f"  scheme: {uri.get('scheme')}")
        print(f"  hosts: {uri.get('host_count')}")
        print(f"  tls: {uri.get('tls')}")
        print(f"  tls_insecure: {uri.get('tls_insecure')}")
        if uri.get("parse_error"):
            print(f"  parse_error: {uri['parse_error']}")

    environment = report.get("environment")
    if environment:
        print("Environment:")
        for key, value in environment.items():
            print(f"  {key}: {value}")

    probes = report.get("tls_probes")
    if probes:
        print("TLS probes:")
        for probe in probes:
            if probe.get("ok"):
                print(
                    f"  shard {probe.get('shard')}: OK "
                    f"({probe.get('tls_version')})"
                )
            else:
                print(
                    f"  shard {probe.get('shard')}: FAILED "
                    f"({probe.get('error_category')})"
                )


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Sanitized MongoDB Atlas connectivity check."
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print a machine-readable diagnostic report.",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Include Python/OpenSSL/PyMongo/CA environment details.",
    )
    parser.add_argument(
        "--probe-tls",
        action="store_true",
        help="Probe each SRV host with a direct TLS handshake on failure.",
    )
    args = parser.parse_args(argv)

    settings = get_settings()
    if not args.json:
        print(
            "Checking MongoDB Atlas connection "
            f"(database: {settings.database_name}) ..."
        )

    try:
        result = ping_database()
        report = build_report(
            result,
            settings,
            public_ip=get_public_ip() if not result.get("connected") else None,
            include_environment=args.verbose,
        )
        if args.probe_tls and not result.get("connected"):
            report["tls_probes"] = probe_tls_hosts(settings.mongodb_uri)

        if args.json:
            print(json.dumps(report, indent=2, sort_keys=True))
        else:
            _print_human(report)
        return 0 if report.get("connected") else 1
    finally:
        close_database()


if __name__ == "__main__":
    raise SystemExit(main())
