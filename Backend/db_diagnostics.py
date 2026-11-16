"""Safe MongoDB Atlas connection diagnostics.

The helpers in this module classify driver failures without exposing the
connection string, credentials, or raw driver messages. They are used by
``Backend.database.ping_database`` and the standalone health-check script.

Atlas returns ``TLSV1_ALERT_INTERNAL_ERROR`` (SSL alert 80) before it sends a
certificate when the source IP is not in the cluster's Network Access list.
Free/M0 clusters can also return this when they are paused or unavailable.
The classification below makes that explicit without weakening TLS
verification.
"""

from __future__ import annotations

import ipaddress
import platform
import socket
import ssl
import urllib.request
from importlib import metadata
from typing import Any, Iterable, Mapping, Optional

from pymongo.errors import PyMongoError
from pymongo.uri_parser import parse_uri

# Failure categories. These are stable identifiers safe to expose in health
# responses and logs.
TLS_HANDSHAKE_REJECTED = "tls_handshake_rejected"
TLS_CERTIFICATE_ERROR = "tls_certificate_error"
DNS_ERROR = "dns_error"
AUTHENTICATION_ERROR = "authentication_error"
AUTHORIZATION_ERROR = "authorization_error"
CONNECTION_REFUSED = "connection_refused"
TIMEOUT = "timeout"
NETWORK_ERROR = "network_error"
DATABASE_ERROR = "database_error"
UNKNOWN_ERROR = "unknown_error"

_TLS_ALERT_MARKERS = (
    "tlsv1_alert_internal_error",
    "tlsv1 alert internal error",
    "ssl alert number 80",
    "ssl alert 80",
    "alert number 80",
    "0a000438",
)
_TLS_CERTIFICATE_MARKERS = (
    "certificate_verify_failed",
    "certificate verify failed",
    "unable to get local issuer certificate",
    "hostname mismatch",
    "certificate has expired",
    "self-signed certificate",
    "ip address mismatch",
    "no matching subject alternative name",
)
_DNS_MARKERS = (
    "querysrv",
    "enotfound",
    "etimedout",
    "name or service not known",
    "nodename nor servname provided",
    "temporary failure in name resolution",
    "dns",
)
_AUTHENTICATION_MARKERS = (
    "authentication failed",
    "bad auth",
    "auth failed",
    "scram",
    "sasl",
)
_AUTHORIZATION_MARKERS = (
    "not authorized",
    "unauthorized",
    "requires authentication",
)
_CONNECTION_REFUSED_MARKERS = (
    "connection refused",
    "econnrefused",
    "actively refused",
)
_TIMEOUT_MARKERS = (
    "serverselectiontimeouterror",
    "server selection timeout",
    "timed out",
    "timeouterror",
    "connection timeout",
)
_NETWORK_MARKERS = (
    "networkerror",
    "network error",
    "connection reset",
    "econnreset",
    "broken pipe",
    "no route to host",
    "unreachable",
)

_FAILURE_DETAILS: dict[str, dict[str, tuple[str, ...]]] = {
    TLS_HANDSHAKE_REJECTED: {
        "summary": (
            "Atlas rejected the TLS handshake before exchanging a certificate. "
            "This is not a Python, OpenSSL, PyMongo, or CA-bundle problem."
        ),
        "likely_causes": (
            "The current public IP is not in Atlas > Network Access "
            "(most common for free/M0 clusters).",
            "A temporary Network Access entry expired.",
            "The cluster is paused, deleted, or the connection string is stale.",
        ),
        "next_steps": (
            "Open Atlas > Network Access and add the current public IP as a "
            "permanent entry (for example, 203.0.113.10/32).",
            "Open Atlas > Clusters and confirm the cluster is running. Resume it "
            "if it is paused.",
            "If the cluster was recreated, copy the current connection string "
            "into MONGODB_URI.",
            "Re-run: python -m Backend.scripts.check_db",
        ),
    },
    TLS_CERTIFICATE_ERROR: {
        "summary": "TLS certificate verification failed.",
        "likely_causes": (
            "The operating system or Python CA bundle is missing or outdated.",
            "A proxy, VPN, or antivirus product is intercepting TLS.",
            "The server hostname does not match its certificate.",
        ),
        "next_steps": (
            "Update Python and the operating system CA store.",
            "Disable TLS-intercepting proxies/VPNs for this connection.",
            "Do not set tlsAllowInvalidCertificates or tlsInsecure. Fix the "
            "trust chain instead.",
        ),
    },
    DNS_ERROR: {
        "summary": "MongoDB SRV or hostname resolution failed.",
        "likely_causes": (
            "The DNS resolver cannot reach Atlas SRV records.",
            "A VPN, proxy, or firewall is blocking DNS.",
            "The cluster hostname is incorrect or stale.",
        ),
        "next_steps": (
            "Try a different DNS resolver or network.",
            "Verify the SRV and TXT records for the cluster.",
            "Re-run: python -m Backend.scripts.check_db --verbose",
        ),
    },
    AUTHENTICATION_ERROR: {
        "summary": "Atlas rejected the database credentials.",
        "likely_causes": (
            "The database username or password is incorrect.",
            "The password contains special characters that are not URL-encoded.",
            "The authSource value does not match where the user was created.",
        ),
        "next_steps": (
            "Check the database user in Atlas > Database Access.",
            "URL-encode special characters in the password before placing it "
            "in MONGODB_URI.",
            "Use authSource=admin unless the user was created in another "
            "database.",
        ),
    },
    AUTHORIZATION_ERROR: {
        "summary": "The database user authenticated but lacks permission.",
        "likely_causes": (
            "The database user has insufficient Atlas roles.",
            "The user is authenticating against the wrong database.",
        ),
        "next_steps": (
            "Review the user's roles in Atlas > Database Access.",
            "Use a user with readWrite access to the application database.",
        ),
    },
    CONNECTION_REFUSED: {
        "summary": "The Atlas host refused the TCP connection.",
        "likely_causes": (
            "The cluster is paused or deleted.",
            "The host or port in MONGODB_URI is wrong.",
            "A firewall is blocking outbound TCP 27017.",
        ),
        "next_steps": (
            "Confirm the cluster is running in Atlas > Clusters.",
            "Check the connection string hostnames and port.",
            "Allow outbound TCP 27017 in the local firewall.",
        ),
    },
    TIMEOUT: {
        "summary": "The connection timed out before Atlas responded.",
        "likely_causes": (
            "The current public IP is not in Atlas > Network Access.",
            "The cluster is paused, starting, or under maintenance.",
            "A firewall, VPN, or proxy is blocking TCP 27017.",
        ),
        "next_steps": (
            "Add the current public IP in Atlas > Network Access.",
            "Confirm the cluster is running and not paused.",
            "Check firewall and VPN rules for outbound TCP 27017.",
        ),
    },
    NETWORK_ERROR: {
        "summary": "A network error interrupted the connection.",
        "likely_causes": (
            "A firewall, VPN, or proxy reset the connection.",
            "The network path to Atlas is unstable.",
            "The cluster is temporarily unavailable.",
        ),
        "next_steps": (
            "Retry from a different network.",
            "Disable VPN/proxy TLS inspection for this connection.",
            "Check https://status.mongodb.com for Atlas incidents.",
        ),
    },
    DATABASE_ERROR: {
        "summary": "MongoDB returned an error while handling the request.",
        "likely_causes": (
            "The requested database operation failed.",
            "The cluster is temporarily unavailable.",
        ),
        "next_steps": (
            "Run: python -m Backend.scripts.check_db --verbose",
            "Check https://status.mongodb.com for Atlas incidents.",
        ),
    },
    UNKNOWN_ERROR: {
        "summary": "The connection failed for an unknown reason.",
        "likely_causes": (
            "A driver, network, or Atlas-side error occurred.",
        ),
        "next_steps": (
            "Run: python -m Backend.scripts.check_db --verbose",
            "Check the backend log and https://status.mongodb.com.",
        ),
    },
}

_PUBLIC_IP_URLS = (
    "https://api.ipify.org",
    "https://ifconfig.me/ip",
)


def _contains_any(text: str, markers: Iterable[str]) -> bool:
    return any(marker in text for marker in markers)


def _iter_exceptions(exc: BaseException) -> Iterable[BaseException]:
    """Yield an exception and its nested causes without looping forever."""
    stack: list[BaseException] = [exc]
    seen: set[int] = set()
    while stack:
        current = stack.pop()
        if id(current) in seen:
            continue
        seen.add(id(current))
        yield current

        for attr in ("__cause__", "__context__"):
            nested = getattr(current, attr, None)
            if isinstance(nested, BaseException):
                stack.append(nested)

        # Some wrappers keep the original error in args.
        for arg in getattr(current, "args", ()):
            if isinstance(arg, BaseException):
                stack.append(arg)


def _exception_text(exc: BaseException) -> str:
    parts: list[str] = []
    for item in _iter_exceptions(exc):
        parts.append(type(item).__name__)
        try:
            text = str(item)
        except Exception:  # pragma: no cover - defensive
            text = ""
        if text:
            parts.append(text)
    return " ".join(parts).lower()


def classify_exception(exc: BaseException) -> str:
    """Return a stable, safe failure category for a driver exception."""
    text = _exception_text(exc)

    if _contains_any(text, _TLS_ALERT_MARKERS):
        return TLS_HANDSHAKE_REJECTED
    if _contains_any(text, _TLS_CERTIFICATE_MARKERS):
        return TLS_CERTIFICATE_ERROR
    if _contains_any(text, _DNS_MARKERS):
        return DNS_ERROR
    if _contains_any(text, _AUTHENTICATION_MARKERS):
        return AUTHENTICATION_ERROR
    if _contains_any(text, _AUTHORIZATION_MARKERS):
        return AUTHORIZATION_ERROR
    if _contains_any(text, _CONNECTION_REFUSED_MARKERS):
        return CONNECTION_REFUSED
    if _contains_any(text, _TIMEOUT_MARKERS):
        return TIMEOUT
    if _contains_any(text, _NETWORK_MARKERS):
        return NETWORK_ERROR
    if isinstance(exc, PyMongoError):
        return DATABASE_ERROR
    return UNKNOWN_ERROR


def failure_details(category: str) -> dict[str, tuple[str, ...]]:
    """Return safe, actionable guidance for a failure category."""
    return _FAILURE_DETAILS.get(category, _FAILURE_DETAILS[UNKNOWN_ERROR])


def _truthy(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return bool(value)


def describe_uri(uri: str) -> dict[str, Any]:
    """Describe connection settings without exposing credentials or hosts."""
    scheme = uri.split(":", 1)[0] if ":" in uri else "unknown"
    try:
        parsed = parse_uri(uri)
    except Exception as exc:  # noqa: BLE001 - diagnostic path only
        return {"scheme": scheme, "parse_error": type(exc).__name__}

    options = {
        str(key).lower(): value
        for key, value in (parsed.get("options") or {}).items()
    }
    tls_option = options.get("tls", options.get("ssl"))
    tls_enabled = _truthy(tls_option) if tls_option is not None else scheme == "mongodb+srv"

    return {
        "scheme": scheme,
        "host_count": len(parsed.get("nodelist") or []),
        "database": parsed.get("database") or None,
        "username_present": bool(parsed.get("username")),
        "password_present": bool(parsed.get("password")),
        "tls": tls_enabled,
        "tls_insecure": any(
            _truthy(options.get(name))
            for name in (
                "tlsinsecure",
                "tlsallowinvalidcertificates",
                "tlsallowinvalidhostnames",
            )
        ),
        "auth_source": options.get("authsource"),
        "replica_set": options.get("replicaset"),
        "load_balanced": _truthy(options.get("loadbalanced")),
        "direct_connection": _truthy(options.get("directconnection")),
    }


def _package_version(name: str) -> Optional[str]:
    try:
        return metadata.version(name)
    except metadata.PackageNotFoundError:
        return None


def environment_info() -> dict[str, Any]:
    """Return TLS/runtime versions useful for diagnosing handshake failures."""
    verify_paths = ssl.get_default_verify_paths()
    certifi_bundle = None
    try:
        import certifi  # type: ignore[import-not-found]

        certifi_bundle = certifi.where()
    except Exception:  # pragma: no cover - certifi is optional for diagnostics
        certifi_bundle = None

    return {
        "python": platform.python_version(),
        "openssl": ssl.OPENSSL_VERSION,
        "pymongo": _package_version("pymongo"),
        "dnspython": _package_version("dnspython"),
        "certifi": _package_version("certifi"),
        "platform": platform.platform(),
        "ssl_default_cafile": verify_paths.openssl_cafile,
        "ssl_default_capath": verify_paths.openssl_capath,
        "certifi_bundle": certifi_bundle,
    }


def get_public_ip(timeout: float = 3.0) -> Optional[str]:
    """Best-effort public IPv4 lookup used to make allowlist fixes concrete."""
    for url in _PUBLIC_IP_URLS:
        try:
            request = urllib.request.Request(
                url,
                headers={"User-Agent": "CraftLineAI-DB-Diagnostics/1.0"},
            )
            with urllib.request.urlopen(request, timeout=timeout) as response:
                text = response.read(64).decode("ascii", "ignore").strip()
            ipaddress.ip_address(text)
            return text
        except Exception:  # noqa: BLE001 - diagnostics must never fail hard
            continue
    return None


def probe_tls(
    host: str,
    port: int = 27017,
    *,
    server_hostname: Optional[str] = None,
    timeout: float = 5.0,
) -> dict[str, Any]:
    """Perform a direct TLS handshake and return a safe result summary."""
    context = ssl.create_default_context()
    try:
        with socket.create_connection((host, port), timeout=timeout) as raw:
            with context.wrap_socket(
                raw, server_hostname=server_hostname or host
            ) as tls:
                cipher = tls.cipher()
                return {
                    "ok": True,
                    "tls_version": tls.version(),
                    "cipher": cipher[0] if cipher else None,
                }
    except Exception as exc:  # noqa: BLE001 - diagnostic path only
        return {
            "ok": False,
            "error": type(exc).__name__,
            "error_category": classify_exception(exc),
        }


def probe_tls_hosts(uri: str, timeout: float = 3.0) -> list[dict[str, Any]]:
    """Probe each SRV host without exposing hostnames in the result."""
    try:
        parsed = parse_uri(uri)
    except Exception as exc:  # noqa: BLE001 - diagnostic path only
        return [{"shard": 0, "ok": False, "error_category": classify_exception(exc)}]

    results: list[dict[str, Any]] = []
    for index, (host, port) in enumerate(parsed.get("nodelist") or []):
        result = probe_tls(host, port, timeout=timeout)
        result["shard"] = index
        results.append(result)
    return results


def build_report(
    ping_result: Mapping[str, Any],
    settings: Any,
    *,
    public_ip: Optional[str] = None,
    include_environment: bool = False,
    tls_probes: Optional[list[dict[str, Any]]] = None,
) -> dict[str, Any]:
    """Build a safe diagnostic report from a ping result and settings."""
    report: dict[str, Any] = dict(ping_result)
    report["uri"] = describe_uri(settings.mongodb_uri)

    if public_ip:
        report["public_ip"] = public_ip
    if include_environment:
        report["environment"] = environment_info()
    if tls_probes is not None:
        report["tls_probes"] = tls_probes

    if not report.get("connected"):
        category = report.get("error_category") or UNKNOWN_ERROR
        details = failure_details(category)
        report["error_category"] = category
        report["hint"] = details["summary"]
        report["likely_causes"] = list(details["likely_causes"])
        report["next_steps"] = list(details["next_steps"])

    return report
