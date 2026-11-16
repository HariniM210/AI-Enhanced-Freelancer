"""CraftLine AI — FastAPI application entry point.

Phase 1 provides meta/health endpoints; Phase 2 adds authentication; Phase 3
adds freelancer profiles and client project management; Phase 4 adds project
applications and the single-hire workflow; Phase 5 adds the Random Forest
freelancer-project matching service; Phase 6 adds Gemini-backed proposal and
profile-summary generation with human review before use.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pymongo.errors import PyMongoError

from Backend.config import get_settings
from Backend.database import close_database, ensure_indexes, ping_database
from Backend.routes.ai import router as ai_router
from Backend.routes.applications import (
    project_applications_router,
    router as applications_router,
)
from Backend.routes.auth import router as auth_router
from Backend.routes.freelancers import router as freelancers_router
from Backend.routes.ml import router as ml_router
from Backend.routes.projects import router as projects_router
from Backend.services.ml_service import warm_model

logger = logging.getLogger(__name__)


def configure_logging(debug: bool) -> None:
    logging.basicConfig(
        level=logging.DEBUG if debug else logging.INFO,
        format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    )
    # Third-party libraries log connection metadata at DEBUG level, including
    # cluster hostnames. Keep them at WARNING regardless of DEBUG.
    for noisy_logger in ("pymongo", "httpx", "httpx2", "httpcore", "httpcore2"):
        logging.getLogger(noisy_logger).setLevel(logging.WARNING)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup/shutdown work: verify Atlas and create indexes."""
    settings = get_settings()
    configure_logging(settings.debug)
    logger.info("Starting %s v%s", settings.app_name, settings.app_version)

    result = ping_database()
    if result["connected"]:
        logger.info(
            "MongoDB Atlas connection OK (database='%s', %sms).",
            result["database"],
            result["latency_ms"],
        )
        try:
            ensure_indexes()
        except Exception as exc:  # noqa: BLE001 - startup must not leak details
            logger.warning("Could not ensure MongoDB indexes (%s).", type(exc).__name__)
    else:
        logger.warning(
            "MongoDB Atlas is not reachable (database='%s'). /health will report it.",
            result["database"],
        )

    # Load the matching model once at startup. A missing model is logged and
    # leaves the rest of the API available; ML routes return 503 in that case.
    warm_model()

    yield

    close_database()
    logger.info("Shutdown complete.")


def create_app() -> FastAPI:
    """Application factory, kept separate so tests can build fresh instances."""
    settings = get_settings()

    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description="AI-enhanced freelancer works platform API.",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(auth_router)
    app.include_router(freelancers_router)
    app.include_router(projects_router)
    app.include_router(applications_router)
    app.include_router(project_applications_router)
    app.include_router(ml_router)
    app.include_router(ai_router)

    @app.get("/", tags=["meta"])
    def root() -> dict:
        return {
            "name": settings.app_name,
            "version": settings.app_version,
            "docs": "/docs",
            "health": "/health",
        }

    @app.get("/health", tags=["meta"])
    def health():
        """Overall health: the API process plus the MongoDB Atlas ping."""
        db = ping_database()
        healthy = bool(db["connected"])
        database_payload = {
            "status": "connected" if healthy else "unavailable",
            "name": db["database"],
            "latency_ms": db["latency_ms"],
        }
        if not healthy:
            # Safe, stable diagnostic fields. No hosts or credentials.
            database_payload["error_category"] = db.get(
                "error_category", "unknown_error"
            )
            database_payload["hint"] = db.get(
                "hint", "Database service is unavailable."
            )
        payload = {
            "status": "ok" if healthy else "degraded",
            "app": settings.app_name,
            "version": settings.app_version,
            "database": database_payload,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        return JSONResponse(status_code=200 if healthy else 503, content=payload)

    @app.get("/health/db", tags=["meta"])
    def health_db():
        """Database-only health check."""
        db = ping_database()
        return JSONResponse(status_code=200 if db["connected"] else 503, content=db)

    @app.exception_handler(PyMongoError)
    async def mongo_exception_handler(request: Request, exc: PyMongoError):
        """Report database outages as 503 without leaking driver details."""
        logger.error(
            "MongoDB error on %s %s (%s)",
            request.method,
            request.url.path,
            type(exc).__name__,
        )
        return JSONResponse(
            status_code=503,
            content={"detail": "Database service is unavailable. Please try again."},
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception):
        """Return a generic error and keep stack traces in the server log."""
        logger.exception("Unhandled error on %s %s", request.method, request.url.path)
        return JSONResponse(status_code=500, content={"detail": "Internal server error."})

    return app


app = create_app()
