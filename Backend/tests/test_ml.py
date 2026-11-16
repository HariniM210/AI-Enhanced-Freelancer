"""Phase 5 ML matching tests.

The suite uses the in-memory ``domain_db`` fixture and the real trained model
artifact. It never contacts MongoDB Atlas or any external AI service.
"""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

import pandas as pd
import pytest
from bson import ObjectId

from Backend.services import ml_service
from ML.features import (
    FEATURE_COLUMNS,
    LABELS,
    MODERATE_THRESHOLD,
    STRONG_THRESHOLD,
    compute_match_score,
    extract_match_features,
    label_for_score,
    normalize_skill,
)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATASET_PATH = PROJECT_ROOT / "ML" / "dataset" / "synthetic_freelancer_project_matches.csv"


def _headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _register_freelancer(
    client,
    *,
    email: str,
    name: str = "Aarav Sharma",
    years_experience: int = 3,
) -> dict:
    response = client.post(
        "/auth/register",
        json={
            "name": name,
            "email": email,
            "password": "Passw0rd1",
            "role": "freelancer",
            "headline": "Full-stack developer",
            "years_experience": years_experience,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def _register_client(
    client,
    *,
    email: str,
    name: str = "Priya Nair",
    company_name: str = "Northwind Logistics",
) -> dict:
    response = client.post(
        "/auth/register",
        json={
            "name": name,
            "email": email,
            "password": "Passw0rd1",
            "role": "client",
            "company_name": company_name,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def _set_profile(domain_db, user_id: str, **fields) -> None:
    result = domain_db.freelancers.update_one(
        {"_id": ObjectId(user_id)},
        {"$set": fields},
    )
    assert result.matched_count == 1, "The auth registration should create a profile."


def _project_payload(**overrides) -> dict:
    payload = {
        "title": "Build a REST API for logistics",
        "category": "Backend & APIs",
        "description": (
            "We need a secure REST API with authentication, project "
            "management, and reporting endpoints for our logistics platform."
        ),
        "skills": ["Python", "FastAPI", "MongoDB"],
        "experience_level": "Intermediate",
        "budget_type": "fixed",
        "budget_min": 1200,
        "budget_max": 2000,
        "currency": "USD",
        "deadline": (date.today() + timedelta(days=30)).isoformat(),
        "duration": "6 weeks",
        "requirements": ["Design the API", "Write automated tests"],
    }
    payload.update(overrides)
    return payload


def _create_project(client, token: str, **overrides) -> dict:
    response = client.post(
        "/projects",
        json=_project_payload(**overrides),
        headers=_headers(token),
    )
    assert response.status_code == 201, response.text
    return response.json()


def _predict(client, token: str, freelancer_id: str, project_id: str):
    return client.post(
        "/ml/predict-match",
        json={"freelancer_id": freelancer_id, "project_id": project_id},
        headers=_headers(token),
    )


def _strong_profile() -> dict:
    return {
        "skills": ["Python", "FastAPI", "MongoDB", "Docker", "AWS"],
        "years_experience": 8,
        "experience_level": "Expert",
        "avg_rating": 4.9,
        "portfolio": [
            {
                "title": "API platform",
                "description": "Built Python FastAPI MongoDB services.",
                "url": "https://example.invalid/one",
                "technologies": ["Python", "FastAPI", "MongoDB"],
            },
            {
                "title": "Cloud migration",
                "description": "MongoDB and Docker deployment.",
                "url": "https://example.invalid/two",
                "technologies": ["MongoDB", "Docker"],
            },
        ],
        "work_history": [
            {
                "role": "Backend Engineer",
                "company": "Acme",
                "period": "2018 - 2024",
                "description": "Built Python FastAPI MongoDB services.",
            },
            {
                "role": "Senior Engineer",
                "company": "Globex",
                "period": "2024 - 2026",
                "description": "Led FastAPI and MongoDB projects.",
            },
        ],
    }


def _moderate_profile() -> dict:
    return {
        "skills": ["Python", "FastAPI"],
        "years_experience": 4,
        "experience_level": "Intermediate",
        "avg_rating": 3.5,
        "portfolio": [
            {
                "title": "Small API",
                "description": "Built a Python service.",
                "url": "https://example.invalid/three",
                "technologies": ["Python"],
            }
        ],
        "work_history": [
            {
                "role": "Developer",
                "company": "Initech",
                "period": "2021 - 2024",
                "description": "Used Python for internal tools.",
            }
        ],
    }


def _low_profile() -> dict:
    return {
        "skills": ["Figma", "UI Design"],
        "years_experience": 0,
        "experience_level": "Entry",
        "avg_rating": 0.0,
        "portfolio": [],
        "work_history": [],
    }


# ---------------------------------------------------------------------------
# Dataset and feature engineering
# ---------------------------------------------------------------------------


def test_dataset_is_synthetic_and_valid():
    assert DATASET_PATH.exists(), "Run python -m ML.scripts.generate_dataset first."
    dataframe = pd.read_csv(DATASET_PATH)

    assert len(dataframe) == 1500
    assert set(FEATURE_COLUMNS).issubset(dataframe.columns)
    assert set(dataframe["label"].unique()) == set(LABELS)
    assert not dataframe[list(FEATURE_COLUMNS) + ["label"]].isna().any().any()
    assert dataframe.duplicated(subset=list(FEATURE_COLUMNS)).sum() == 0
    assert dataframe["skills_match_percentage"].between(0, 100).all()
    assert dataframe["required_technology_match"].between(0, 100).all()
    assert dataframe["avg_rating"].between(0, 5).all()
    assert dataframe["years_experience"].between(0, 60).all()
    assert dataframe["category_relevance"].between(0, 1).all()
    assert dataframe["experience_level_compatibility"].between(0, 1).all()
    assert dataframe["portfolio_evidence"].between(0, 1).all()
    assert dataframe["work_history_evidence"].between(0, 1).all()


def test_feature_extraction_for_strong_profile():
    project = {
        "skills": ["Python", "FastAPI", "MongoDB"],
        "category": "Backend & APIs",
        "experience_level": "Intermediate",
    }
    features = extract_match_features(_strong_profile(), project)

    assert features["skills_match_percentage"] == 100.0
    assert features["required_technology_match"] == 100.0
    assert features["category_relevance"] == 1.0
    assert features["years_experience"] == 8
    assert features["experience_level_compatibility"] == 0.5
    assert features["avg_rating"] == 4.9
    assert features["portfolio_evidence"] == 1.0
    assert features["work_history_evidence"] == 1.0
    assert features["matched_skills"] == ["FastAPI", "MongoDB", "Python"]
    assert features["missing_skills"] == []
    assert features["required_technology_count"] == 3
    assert features["matched_technology_count"] == 3
    assert features["project_category"] == "Backend & APIs"
    assert features["freelancer_experience_level"] == "Expert"


def test_feature_extraction_handles_missing_optional_fields():
    features = extract_match_features({}, {})

    assert features["skills_match_percentage"] == 0.0
    assert features["required_technology_match"] == 0.0
    assert features["category_relevance"] == 0.0
    assert features["years_experience"] == 0
    assert features["experience_level_compatibility"] == 0.5
    assert features["avg_rating"] == 0.0
    assert features["portfolio_evidence"] == 0.0
    assert features["work_history_evidence"] == 0.0
    assert features["matched_skills"] == []
    assert features["missing_skills"] == []
    assert features["required_technologies"] == []
    assert features["project_experience_level"] is None


def test_skill_aliases_are_normalized():
    assert normalize_skill("REST API") == "rest apis"
    assert normalize_skill("NodeJS") == "node.js"
    assert normalize_skill("HTML5") == "html/css"

    features = extract_match_features(
        {"skills": ["REST API", "NodeJS"]},
        {"skills": ["REST APIs", "Node.js"], "category": "Backend & APIs"},
    )
    assert features["skills_match_percentage"] == 100.0


def test_expanded_category_taxonomy_supports_live_matching():
    features = extract_match_features(
        {"skills": ["Python", "TensorFlow", "PyTorch"]},
        {
            "skills": ["Python", "TensorFlow", "PyTorch"],
            "category": "AI & Generative AI",
        },
    )

    assert features["project_category"] == "AI & Generative AI"
    assert features["category_relevance"] == 1.0


def test_rubric_boundaries_and_scores():
    assert label_for_score(STRONG_THRESHOLD) == "Strong Match"
    assert label_for_score(STRONG_THRESHOLD - 0.01) == "Moderate Match"
    assert label_for_score(MODERATE_THRESHOLD) == "Moderate Match"
    assert label_for_score(MODERATE_THRESHOLD - 0.01) == "Low Match"

    features = extract_match_features(_strong_profile(), _project_payload())
    score = compute_match_score(features)
    assert 0 <= score <= 100
    assert label_for_score(score) in LABELS


# ---------------------------------------------------------------------------
# Model loading and prediction
# ---------------------------------------------------------------------------


def test_model_loads_once_and_has_metadata():
    bundle = ml_service.load_model()
    assert bundle is ml_service.load_model()
    assert bundle["metadata"]["model_version"] == "phase5-rf-v1"
    assert set(bundle["classes"]) == set(LABELS)
    assert bundle["feature_columns"] == list(FEATURE_COLUMNS)


def test_prediction_paths_strong_moderate_low(client, domain_db):
    client_account = _register_client(client, email="client@example.com")
    project = _create_project(client, client_account["access_token"])

    cases = [
        ("strong@example.com", "Strong Match", _strong_profile()),
        ("moderate@example.com", "Moderate Match", _moderate_profile()),
        ("low@example.com", "Low Match", _low_profile()),
    ]
    for email, expected_label, profile in cases:
        freelancer = _register_freelancer(client, email=email)
        _set_profile(domain_db, freelancer["user"]["id"], **profile)
        response = _predict(
            client,
            freelancer["access_token"],
            freelancer["user"]["id"],
            project["id"],
        )
        assert response.status_code == 200, response.text
        assert response.json()["label"] == expected_label


def test_prediction_supports_new_project_category(client, domain_db):
    client_account = _register_client(client, email="new-category-client@example.com")
    freelancer = _register_freelancer(
        client, email="new-category-freelancer@example.com"
    )
    _set_profile(
        domain_db,
        freelancer["user"]["id"],
        skills=["Python", "TensorFlow", "PyTorch"],
        years_experience=5,
        experience_level="Expert",
        avg_rating=4.8,
    )
    project = _create_project(
        client,
        client_account["access_token"],
        title="Build a generative AI assistant",
        category="AI & Generative AI",
        skills=["Python", "TensorFlow", "PyTorch"],
    )

    response = _predict(
        client,
        freelancer["access_token"],
        freelancer["user"]["id"],
        project["id"],
    )
    assert response.status_code == 200, response.text
    body = response.json()

    assert body["features"]["project_category"] == "AI & Generative AI"
    assert body["features"]["category_relevance"] == 1.0
    assert body["label"] in LABELS


def test_valid_prediction_response_schema(client, domain_db):
    client_account = _register_client(client, email="schema-client@example.com")
    freelancer = _register_freelancer(client, email="schema-freelancer@example.com")
    _set_profile(domain_db, freelancer["user"]["id"], **_strong_profile())
    project = _create_project(client, client_account["access_token"])

    response = _predict(
        client,
        freelancer["access_token"],
        freelancer["user"]["id"],
        project["id"],
    )
    assert response.status_code == 200, response.text
    body = response.json()

    assert body["freelancer_id"] == freelancer["user"]["id"]
    assert body["project_id"] == project["id"]
    assert body["label"] in LABELS
    assert 0 <= body["confidence"] <= 1
    assert 0 <= body["rubric_score"] <= 100
    assert 0 <= body["match_percentage"] <= 100
    assert 0 <= body["expected_match_score"] <= 100
    assert body["rubric_score"] == compute_match_score(body["features"])
    assert body["match_percentage"] == round(body["confidence"] * 100, 2)
    assert body["model_version"] == "phase5-rf-v1"
    assert set(body["probabilities"]) == {"strong", "moderate", "low"}
    assert abs(sum(body["probabilities"].values()) - 1.0) < 0.001
    assert set(body["features"]) >= {
        "skills_match_percentage",
        "required_technology_match",
        "category_relevance",
        "years_experience",
        "experience_level_compatibility",
        "avg_rating",
        "portfolio_evidence",
        "work_history_evidence",
        "matched_skills",
        "missing_skills",
        "required_technologies",
        "matched_technologies",
        "missing_technologies",
        "required_technology_count",
        "matched_technology_count",
        "project_category",
        "experience_level",
        "freelancer_experience_level",
        "project_experience_level",
    }
    assert "email" not in body
    assert "password_hash" not in body
    assert "user_id" not in body


def test_rubric_score_is_calculated_from_live_features(client, domain_db):
    client_account = _register_client(client, email="rubric-client@example.com")
    freelancer = _register_freelancer(client, email="rubric-freelancer@example.com")
    _set_profile(domain_db, freelancer["user"]["id"], **_strong_profile())
    project = _create_project(client, client_account["access_token"])

    response = _predict(
        client,
        freelancer["access_token"],
        freelancer["user"]["id"],
        project["id"],
    )
    assert response.status_code == 200, response.text
    body = response.json()

    assert body["label"] == "Strong Match"
    assert body["rubric_score"] == compute_match_score(body["features"])
    assert body["rubric_score"] >= STRONG_THRESHOLD
    assert abs(body["confidence"] - max(body["probabilities"].values())) < 1e-6
    # The legacy field remains a confidence alias, not a fit score.
    assert body["match_percentage"] == round(body["confidence"] * 100, 2)


def test_openapi_documents_rubric_score_and_deprecated_match_percentage(client):
    spec = client.get("/openapi.json").json()
    schemas = spec["components"]["schemas"]

    for schema_name in ("MatchPrediction", "RankedFreelancerMatch"):
        properties = schemas[schema_name]["properties"]
        assert "rubric_score" in properties
        assert "confidence" in properties
        assert "match_percentage" in properties

    prediction = schemas["MatchPrediction"]["properties"]
    assert "deprecated" in prediction["match_percentage"]["description"].lower()
    assert "rubric_score" in prediction["rubric_score"]["description"].lower()


def test_prediction_requires_authentication(client, domain_db):
    response = client.post(
        "/ml/predict-match",
        json={"freelancer_id": str(ObjectId()), "project_id": str(ObjectId())},
    )
    assert response.status_code == 401
    assert response.headers.get("www-authenticate") == "Bearer"
    assert response.json()["detail"] == "Authentication required."


def test_prediction_missing_freelancer_profile(client, domain_db):
    client_account = _register_client(client, email="missing-profile-client@example.com")
    project = _create_project(client, client_account["access_token"])

    # A client account has no freelancer profile. The service must not create
    # one and must return a clean 404.
    response = _predict(
        client,
        client_account["access_token"],
        client_account["user"]["id"],
        project["id"],
    )
    assert response.status_code == 404
    assert response.json()["detail"] == "Freelancer profile not found."


def test_prediction_missing_project(client, domain_db):
    freelancer = _register_freelancer(client, email="missing-project@example.com")
    _set_profile(domain_db, freelancer["user"]["id"], **_strong_profile())

    response = _predict(
        client,
        freelancer["access_token"],
        freelancer["user"]["id"],
        str(ObjectId()),
    )
    assert response.status_code == 404
    assert response.json()["detail"] == "Project not found."


@pytest.mark.parametrize("field", ["freelancer_id", "project_id"])
def test_prediction_invalid_ids(client, domain_db, field):
    freelancer = _register_freelancer(
        client, email=f"invalid-{field}@example.com"
    )
    payload = {
        "freelancer_id": freelancer["user"]["id"],
        "project_id": str(ObjectId()),
    }
    payload[field] = "not-an-object-id"

    response = client.post(
        "/ml/predict-match",
        json=payload,
        headers=_headers(freelancer["access_token"]),
    )
    assert response.status_code == 404
    assert response.json()["detail"] in {
        "Freelancer profile not found.",
        "Project not found.",
    }


def test_prediction_rejects_client_supplied_scores(client, domain_db):
    freelancer = _register_freelancer(client, email="extra-fields@example.com")
    response = client.post(
        "/ml/predict-match",
        json={
            "freelancer_id": freelancer["user"]["id"],
            "project_id": str(ObjectId()),
            "skills_match_percentage": 100,
            "label": "Strong Match",
        },
        headers=_headers(freelancer["access_token"]),
    )
    assert response.status_code == 422


def test_model_unavailable_returns_503(client, domain_db, monkeypatch):
    freelancer = _register_freelancer(client, email="model-down@example.com")
    client_account = _register_client(client, email="model-down-client@example.com")
    _set_profile(domain_db, freelancer["user"]["id"], **_strong_profile())
    project = _create_project(client, client_account["access_token"])

    ml_service.reset_model_cache()
    monkeypatch.setattr(ml_service, "MODEL_PATH", Path("missing-model.joblib"))
    ml_service.reset_model_cache()
    try:
        response = _predict(
            client,
            freelancer["access_token"],
            freelancer["user"]["id"],
            project["id"],
        )
        assert response.status_code == 503
        assert "unavailable" in response.json()["detail"].lower()
    finally:
        ml_service.reset_model_cache()


# ---------------------------------------------------------------------------
# Client-only ranking
# ---------------------------------------------------------------------------


def _ranking_setup(client, domain_db, *, owner_email: str = "rank-owner@example.com"):
    owner = _register_client(client, email=owner_email)
    project = _create_project(client, owner["access_token"])

    strong = _register_freelancer(client, email="rank-strong@example.com")
    moderate = _register_freelancer(client, email="rank-moderate@example.com")
    low = _register_freelancer(client, email="rank-low@example.com")
    _set_profile(domain_db, strong["user"]["id"], **_strong_profile())
    _set_profile(domain_db, moderate["user"]["id"], **_moderate_profile())
    _set_profile(domain_db, low["user"]["id"], **_low_profile())
    return owner, project, strong, moderate, low


def test_ranking_requires_authentication(client, domain_db):
    response = client.get(f"/ml/projects/{ObjectId()}/matches")
    assert response.status_code == 401
    assert response.headers.get("www-authenticate") == "Bearer"


def test_ranking_requires_client_role(client, domain_db):
    freelancer = _register_freelancer(client, email="rank-freelancer@example.com")
    response = client.get(
        f"/ml/projects/{ObjectId()}/matches",
        headers=_headers(freelancer["access_token"]),
    )
    assert response.status_code == 403
    assert (
        response.json()["detail"]
        == "You do not have permission to perform this action."
    )


def test_ranking_requires_project_owner(client, domain_db):
    owner, project, _, _, _ = _ranking_setup(client, domain_db)
    other = _register_client(client, email="rank-other@example.com")

    response = client.get(
        f"/ml/projects/{project['id']}/matches",
        headers=_headers(other["access_token"]),
    )
    assert response.status_code == 403
    assert "permission" in response.json()["detail"].lower()


def test_ranking_returns_sorted_public_profiles(client, domain_db):
    owner, project, strong, moderate, low = _ranking_setup(client, domain_db)

    response = client.get(
        f"/ml/projects/{project['id']}/matches",
        headers=_headers(owner["access_token"]),
    )
    assert response.status_code == 200, response.text
    body = response.json()

    assert body["project_id"] == project["id"]
    assert body["total"] == 3
    assert body["model_version"] == "phase5-rf-v1"
    assert len(body["items"]) == 3
    assert [item["label"] for item in body["items"]] == [
        "Strong Match",
        "Moderate Match",
        "Low Match",
    ]
    scores = [item["expected_match_score"] for item in body["items"]]
    assert scores == sorted(scores, reverse=True)
    assert body["items"][0]["freelancer"]["id"] == strong["user"]["id"]
    assert body["items"][-1]["freelancer"]["id"] == low["user"]["id"]

    for item in body["items"]:
        freelancer = item["freelancer"]
        assert "email" not in freelancer
        assert "password_hash" not in freelancer
        assert "user_id" not in freelancer
        assert set(item["probabilities"]) == {"strong", "moderate", "low"}
        assert "features" in item
        assert 0 <= item["rubric_score"] <= 100
        assert item["rubric_score"] == compute_match_score(item["features"])
        assert item["match_percentage"] == round(item["confidence"] * 100, 2)


def test_ranking_limit_and_total(client, domain_db):
    owner, project, _, _, _ = _ranking_setup(
        client, domain_db, owner_email="rank-limit-owner@example.com"
    )
    response = client.get(
        f"/ml/projects/{project['id']}/matches?limit=1",
        headers=_headers(owner["access_token"]),
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["total"] == 3
    assert len(body["items"]) == 1
    assert body["items"][0]["label"] == "Strong Match"


def test_ranking_unknown_project(client, domain_db):
    owner = _register_client(client, email="rank-unknown@example.com")
    response = client.get(
        f"/ml/projects/{ObjectId()}/matches",
        headers=_headers(owner["access_token"]),
    )
    assert response.status_code == 404
    assert response.json()["detail"] == "Project not found."


def test_ranking_model_unavailable_returns_503(client, domain_db, monkeypatch):
    owner, project, _, _, _ = _ranking_setup(
        client, domain_db, owner_email="rank-model-down@example.com"
    )

    ml_service.reset_model_cache()
    monkeypatch.setattr(ml_service, "MODEL_PATH", Path("missing-model.joblib"))
    ml_service.reset_model_cache()
    try:
        response = client.get(
            f"/ml/projects/{project['id']}/matches",
            headers=_headers(owner["access_token"]),
        )
        assert response.status_code == 503
        assert "unavailable" in response.json()["detail"].lower()
    finally:
        ml_service.reset_model_cache()
