"""MongoDB Atlas connection management.

The client is created lazily so importing this module never opens a socket.
Call :func:`ping_database` for a sanitized connectivity check and
:func:`ensure_indexes` once at startup.
"""

from __future__ import annotations

import logging
import time
from typing import Optional

from pymongo import ASCENDING, DESCENDING, MongoClient
from pymongo.database import Database
from pymongo.errors import PyMongoError

from Backend.config import get_settings
from Backend.db_diagnostics import classify_exception, failure_details

logger = logging.getLogger(__name__)

_client: Optional[MongoClient] = None


def get_client() -> MongoClient:
    """Return the shared MongoClient, creating it on first use."""
    global _client
    if _client is None:
        settings = get_settings()
        _client = MongoClient(
            settings.mongodb_uri,
            serverSelectionTimeoutMS=settings.mongodb_timeout_ms,
            connectTimeoutMS=settings.mongodb_timeout_ms,
            socketTimeoutMS=max(settings.mongodb_timeout_ms, 10_000),
            appname=settings.app_name,
            tz_aware=True,
        )
        # Never log the URI. Only the database name is safe.
        logger.info("MongoDB client created (database='%s').", settings.database_name)
    return _client


def get_database() -> Database:
    """Return the configured application database."""
    return get_client()[get_settings().database_name]


def ping_database() -> dict:
    """Ping MongoDB and return diagnostics that are safe to expose.

    The result never contains the connection string, username, or password.
    """
    settings = get_settings()
    started = time.perf_counter()
    try:
        get_client().admin.command("ping")
        latency_ms = round((time.perf_counter() - started) * 1000, 2)
        return {
            "connected": True,
            "database": settings.database_name,
            "latency_ms": latency_ms,
        }
    except PyMongoError as exc:
        latency_ms = round((time.perf_counter() - started) * 1000, 2)
        # Only the exception class name and a stable category are exposed.
        # Raw driver messages can contain hostnames or credentials.
        category = classify_exception(exc)
        logger.warning(
            "MongoDB ping failed (%s, category=%s).",
            type(exc).__name__,
            category,
        )
        return {
            "connected": False,
            "database": settings.database_name,
            "latency_ms": latency_ms,
            "error": type(exc).__name__,
            "error_category": category,
            "hint": failure_details(category)["summary"],
        }


def ensure_indexes() -> None:
    """Create the indexes the application relies on.

    Safe to run on every startup: MongoDB ignores identical indexes.
    """
    db = get_database()

    # Emails are trimmed and lowercased before every insert, so this unique
    # index also enforces case-insensitive uniqueness.
    db["users"].create_index(
        [("email", ASCENDING)], unique=True, name="users_email_unique"
    )
    db["users"].create_index([("role", ASCENDING)], name="users_role")

    db["freelancers"].create_index([("skills", ASCENDING)], name="freelancers_skills")
    db["freelancers"].create_index(
        [("avg_rating", DESCENDING)], name="freelancers_rating"
    )

    db["projects"].create_index(
        [("status", ASCENDING), ("created_at", DESCENDING)],
        name="projects_status_created",
    )
    db["projects"].create_index([("client_id", ASCENDING)], name="projects_client")
    db["projects"].create_index([("category", ASCENDING)], name="projects_category")
    db["projects"].create_index([("skills", ASCENDING)], name="projects_skills")

    db["applications"].create_index(
        [("project_id", ASCENDING), ("freelancer_id", ASCENDING)],
        unique=True,
        name="applications_unique_pair",
    )
    db["applications"].create_index(
        [("freelancer_id", ASCENDING)], name="applications_freelancer"
    )
    db["applications"].create_index(
        [("project_id", ASCENDING)], name="applications_project"
    )
    db["applications"].create_index(
        [("client_id", ASCENDING)], name="applications_client"
    )
    db["applications"].create_index(
        [("project_id", ASCENDING), ("status", ASCENDING)],
        name="applications_project_status",
    )
    db["applications"].create_index(
        [("freelancer_id", ASCENDING), ("created_at", DESCENDING)],
        name="applications_freelancer_created",
    )
    db["applications"].create_index(
        [("client_id", ASCENDING), ("created_at", DESCENDING)],
        name="applications_client_created",
    )

    logger.info("MongoDB indexes ensured.")


def close_database() -> None:
    """Close the shared client (used on application shutdown)."""
    global _client
    if _client is not None:
        _client.close()
        _client = None
        logger.info("MongoDB client closed.")
