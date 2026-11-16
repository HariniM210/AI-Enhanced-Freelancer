"""Phase 5 ML matching service.

The trained Joblib model is loaded once through a lock-protected singleton and
reused by every request. Feature extraction is shared with the dataset and
training scripts in ``ML.features`` so training and serving cannot drift.

Security notes:
- Only public profile/project fields are read for features.
- The browser cannot submit feature values or probabilities.
- Ranking is restricted to the project owner in the route layer and checked
  again here.
"""

from __future__ import annotations

import json
import logging
import threading
from pathlib import Path
from typing import Any, Optional

import joblib
from bson import ObjectId
from bson.errors import InvalidId

from Backend.database import get_database
from Backend.services.freelancer_service import (
    get_freelancer_profile,
    public_freelancer,
)
from ML.features import (
    FEATURE_COLUMNS,
    LABELS,
    compute_match_score,
    extract_match_features,
    feature_vector,
)

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
MODEL_PATH = PROJECT_ROOT / "ML" / "models" / "match_model.joblib"
METADATA_PATH = PROJECT_ROOT / "ML" / "models" / "model_metadata.json"

MAX_RANKING_CANDIDATES = 500

_model_bundle: Optional[dict[str, Any]] = None
_model_lock = threading.Lock()


class MLServiceError(Exception):
    """Base class for expected ML service failures."""


class ModelUnavailableError(MLServiceError):
    """The saved model or metadata could not be loaded."""


class FreelancerNotFoundError(MLServiceError):
    """No freelancer profile exists for the supplied id."""


class ProjectNotFoundError(MLServiceError):
    """No project exists for the supplied id."""


class ProjectAccessDeniedError(MLServiceError):
    """The authenticated client does not own the project."""


def _collection(name: str):
    return get_database()[name]


def _as_object_id(value: str) -> Optional[ObjectId]:
    try:
        return ObjectId(str(value))
    except (InvalidId, TypeError):
        return None


def reset_model_cache() -> None:
    """Clear the singleton. Used by tests that simulate a missing model."""
    global _model_bundle
    with _model_lock:
        _model_bundle = None


def load_model() -> dict[str, Any]:
    """Load and cache the Joblib model plus its metadata.

    Raises:
        ModelUnavailableError: if the model or metadata is missing/corrupt.
    """
    global _model_bundle
    if _model_bundle is not None:
        return _model_bundle

    with _model_lock:
        if _model_bundle is not None:
            return _model_bundle

        if not MODEL_PATH.exists():
            raise ModelUnavailableError(
                "Match model is not available. Train it with "
                "python -m ML.scripts.train_model."
            )
        if not METADATA_PATH.exists():
            raise ModelUnavailableError(
                "Match model metadata is not available. Retrain the model."
            )

        try:
            model = joblib.load(MODEL_PATH)
            metadata = json.loads(METADATA_PATH.read_text(encoding="utf-8"))
        except Exception as exc:  # noqa: BLE001 - hide loader details from clients
            logger.exception("Could not load ML match model")
            raise ModelUnavailableError("Match model is not available.") from exc

        classifier = (
            model.named_steps["classifier"]
            if hasattr(model, "named_steps") and "classifier" in model.named_steps
            else model
        )
        classes = [str(label) for label in getattr(classifier, "classes_", [])]
        if not classes:
            raise ModelUnavailableError("Match model has no classes.")
        if set(classes) != set(LABELS):
            raise ModelUnavailableError(
                "Match model classes do not match the Phase 5 label contract."
            )

        feature_columns = list(
            metadata.get("dataset", {}).get("feature_columns", FEATURE_COLUMNS)
        )
        if feature_columns != list(FEATURE_COLUMNS):
            raise ModelUnavailableError(
                "Match model feature order does not match ML.features.FEATURE_COLUMNS."
            )

        _model_bundle = {
            "model": model,
            "metadata": metadata,
            "classes": classes,
            "feature_columns": feature_columns,
        }
        return _model_bundle


def warm_model() -> None:
    """Best-effort startup warm-up; a missing model must not stop the API."""
    try:
        bundle = load_model()
        logger.info(
            "ML match model loaded (version=%s, classes=%s).",
            bundle["metadata"].get("model_version", "unknown"),
            ", ".join(bundle["classes"]),
        )
    except ModelUnavailableError as exc:
        logger.warning("ML match model unavailable at startup: %s", exc)


def model_metadata() -> dict[str, Any]:
    """Return a copy of the loaded model metadata."""
    return dict(load_model()["metadata"])


def _format_prediction(
    probabilities: Any,
    classes: list[str],
    features: dict[str, Any],
    metadata: dict[str, Any],
) -> dict[str, Any]:
    """Convert raw ``predict_proba`` output into the public response shape.

    The model label and confidence are kept separate from the deterministic
    rubric fit score and the internal ranking score.
    """
    raw = {
        class_name: float(probability)
        for class_name, probability in zip(classes, probabilities)
    }
    class_probabilities = {
        "strong": raw.get("Strong Match", 0.0),
        "moderate": raw.get("Moderate Match", 0.0),
        "low": raw.get("Low Match", 0.0),
    }
    best_index = max(range(len(probabilities)), key=lambda index: probabilities[index])
    label = classes[best_index]
    confidence = float(probabilities[best_index])
    rubric_score = compute_match_score(features)
    expected_match_score = (
        class_probabilities["strong"] * 100.0
        + class_probabilities["moderate"] * 70.0
        + class_probabilities["low"] * 30.0
    )
    return {
        "label": label,
        "rubric_score": rubric_score,
        # Deprecated compatibility alias for predicted-class confidence. This
        # is not a match-quality percentage; use rubric_score for fit.
        "match_percentage": round(confidence * 100.0, 2),
        "confidence": round(confidence, 6),
        "probabilities": {
            key: round(value, 6) for key, value in class_probabilities.items()
        },
        "expected_match_score": round(expected_match_score, 2),
        "model_version": str(metadata.get("model_version", "unknown")),
        "features": features,
    }


def predict_match(freelancer_id: str, project_id: str) -> dict[str, Any]:
    """Predict one freelancer-project match using stored public data."""
    profile = get_freelancer_profile(freelancer_id, create_if_missing=True)
    if profile is None:
        raise FreelancerNotFoundError("Freelancer profile not found.")

    project_object_id = _as_object_id(project_id)
    if project_object_id is None:
        raise ProjectNotFoundError("Project not found.")
    project = _collection("projects").find_one({"_id": project_object_id})
    if project is None:
        raise ProjectNotFoundError("Project not found.")

    bundle = load_model()
    features = extract_match_features(profile, project)
    vector = feature_vector(features)
    probabilities = bundle["model"].predict_proba([vector])[0]
    prediction = _format_prediction(
        probabilities,
        bundle["classes"],
        features,
        bundle["metadata"],
    )
    prediction.update(
        {
            "freelancer_id": str(profile["_id"]),
            "project_id": str(project["_id"]),
        }
    )
    return prediction


def rank_freelancers_for_project(
    project_id: str,
    client: dict[str, Any],
    *,
    limit: int,
) -> dict[str, Any]:
    """Score public freelancer profiles for a client-owned project.

    Only public profile fields are returned. The route already requires the
    client role; ownership is verified again here so the service cannot be
    called unsafely from another route.
    """
    project_object_id = _as_object_id(project_id)
    if project_object_id is None:
        raise ProjectNotFoundError("Project not found.")
    project = _collection("projects").find_one({"_id": project_object_id})
    if project is None:
        raise ProjectNotFoundError("Project not found.")

    client_object_id = _as_object_id(str(client.get("id", "")))
    if client_object_id is None or project.get("client_id") != client_object_id:
        raise ProjectAccessDeniedError(
            "You do not have permission to rank freelancers for this project."
        )

    bundle = load_model()
    profiles = list(
        _collection("freelancers").find({}).limit(MAX_RANKING_CANDIDATES)
    )
    if not profiles:
        return {
            "project_id": str(project["_id"]),
            "items": [],
            "total": 0,
            "model_version": str(bundle["metadata"].get("model_version", "unknown")),
        }

    feature_sets = [extract_match_features(profile, project) for profile in profiles]
    vectors = [feature_vector(features) for features in feature_sets]
    probability_rows = bundle["model"].predict_proba(vectors)

    items: list[dict[str, Any]] = []
    for profile, features, probabilities in zip(
        profiles, feature_sets, probability_rows
    ):
        prediction = _format_prediction(
            probabilities,
            bundle["classes"],
            features,
            bundle["metadata"],
        )
        items.append(
            {
                "freelancer": public_freelancer(profile),
                **prediction,
            }
        )

    items.sort(
        key=lambda item: (
            -float(item["expected_match_score"]),
            str(item["freelancer"].get("name", "")).casefold(),
        )
    )
    total = len(items)
    return {
        "project_id": str(project["_id"]),
        "items": items[:limit],
        "total": total,
        "model_version": str(bundle["metadata"].get("model_version", "unknown")),
    }
