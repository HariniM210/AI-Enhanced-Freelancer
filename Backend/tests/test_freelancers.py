"""Phase 3 freelancer profile tests.

All tests use the shared in-memory ``domain_db`` fixture, so the suite never
contacts MongoDB Atlas.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from bson import ObjectId

FREELANCER = {
    "name": "Aarav Sharma",
    "email": "aarav@example.com",
    "password": "Passw0rd1",
    "role": "freelancer",
    "headline": "Full-stack developer",
    "years_experience": 3,
}

CLIENT = {
    "name": "Priya Nair",
    "email": "priya@example.com",
    "password": "Passw0rd1",
    "role": "client",
    "company_name": "Northwind Logistics",
}


def _headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _register_freelancer(
    client,
    *,
    email: str = "aarav@example.com",
    name: str = "Aarav Sharma",
    headline: str = "Full-stack developer",
    years_experience: int = 3,
):
    payload = {
        **FREELANCER,
        "email": email,
        "name": name,
        "headline": headline,
        "years_experience": years_experience,
    }
    response = client.post("/auth/register", json=payload)
    assert response.status_code == 201, response.text
    return response.json()


def _register_client(client):
    response = client.post("/auth/register", json=CLIENT)
    assert response.status_code == 201, response.text
    return response.json()


# ---------------------------------------------------------------------------
# Reading profiles
# ---------------------------------------------------------------------------


def test_get_freelancer_profile_success(client, domain_db):
    registered = _register_freelancer(client)
    freelancer_id = registered["user"]["id"]

    response = client.get(f"/freelancers/{freelancer_id}")
    assert response.status_code == 200

    body = response.json()
    assert body["id"] == freelancer_id
    assert body["name"] == "Aarav Sharma"
    assert body["headline"] == "Full-stack developer"
    assert body["summary"] == ""
    assert body["location"] == ""
    assert body["availability"] == "Available now"
    assert body["skills"] == []
    assert body["years_experience"] == 3
    assert body["experience_level"] == "Intermediate"
    assert body["hourly_rate"] is None
    assert body["currency"] == "USD"
    assert body["avg_rating"] == 0.0
    assert body["reviews_count"] == 0
    assert body["completed_projects"] == 0
    assert body["avatar_url"] is None
    assert body["portfolio"] == []
    assert body["work_history"] == []

    # Public profile responses must never expose auth or contact fields.
    assert "email" not in body
    assert "password_hash" not in body
    assert FREELANCER["email"] not in response.text


@pytest.mark.parametrize(
    "freelancer_id",
    [str(ObjectId()), "not-an-object-id"],
)
def test_get_freelancer_profile_unknown_returns_404(
    client, domain_db, freelancer_id
):
    response = client.get(f"/freelancers/{freelancer_id}")
    assert response.status_code == 404
    assert response.json()["detail"] == "Freelancer profile not found."


def test_client_id_is_not_a_freelancer_profile(client, domain_db):
    registered = _register_client(client)
    response = client.get(f"/freelancers/{registered['user']['id']}")
    assert response.status_code == 404


def test_get_profile_heals_a_missing_profile_for_an_existing_freelancer(
    client, domain_db
):
    user_id = ObjectId()
    now = datetime.now(timezone.utc)
    domain_db.users.insert_one(
        {
            "_id": user_id,
            "name": "Legacy Freelancer",
            "email": "legacy@example.com",
            "password_hash": "not-a-real-hash",
            "role": "freelancer",
            "headline": "Legacy headline",
            "years_experience": 6,
            "is_active": True,
            "created_at": now,
            "updated_at": now,
        }
    )

    response = client.get(f"/freelancers/{user_id}")
    assert response.status_code == 200

    body = response.json()
    assert body["id"] == str(user_id)
    assert body["name"] == "Legacy Freelancer"
    assert body["headline"] == "Legacy headline"
    assert body["experience_level"] == "Expert"
    assert domain_db.freelancers.find_one({"_id": user_id}) is not None


# ---------------------------------------------------------------------------
# Updating the authenticated freelancer's profile
# ---------------------------------------------------------------------------


def test_update_profile_requires_authentication(client, domain_db):
    response = client.put("/freelancers/profile", json={"summary": "Hello"})
    assert response.status_code == 401
    assert response.headers.get("www-authenticate") == "Bearer"
    assert response.json()["detail"] == "Authentication required."


def test_update_profile_requires_freelancer_role(client, domain_db):
    registered = _register_client(client)
    response = client.put(
        "/freelancers/profile",
        json={"summary": "Hello"},
        headers=_headers(registered["access_token"]),
    )
    assert response.status_code == 403
    assert (
        response.json()["detail"]
        == "You do not have permission to perform this action."
    )


def test_update_profile_summary_only_is_a_partial_update(client, domain_db):
    registered = _register_freelancer(client)

    response = client.put(
        "/freelancers/profile",
        json={"summary": "I build reliable APIs."},
        headers=_headers(registered["access_token"]),
    )
    assert response.status_code == 200, response.text

    body = response.json()
    assert body["summary"] == "I build reliable APIs."
    assert body["name"] == "Aarav Sharma"
    assert body["headline"] == "Full-stack developer"
    assert body["skills"] == []

    stored = domain_db.freelancers.find_one({"_id": ObjectId(body["id"])})
    assert stored["summary"] == "I build reliable APIs."
    assert stored["name"] == "Aarav Sharma"


def test_update_profile_full_payload(client, domain_db):
    registered = _register_freelancer(client)

    payload = {
        "name": "Aarav S. Sharma",
        "headline": "Senior Python developer",
        "location": "Bengaluru, India",
        "availability": "Part-time only",
        "years_experience": 5,
        "experience_level": "Expert",
        "hourly_rate": 45.5,
        "currency": "inr",
        "skills": [" Python ", "python", "FastAPI", "MongoDB"],
        "summary": "I design reliable APIs.",
        "portfolio": [
            {
                "title": "Payments API",
                "description": "A payments service.",
                "url": "https://example.com/payments",
                "technologies": ["FastAPI", "MongoDB"],
            }
        ],
        "work_history": [
            {
                "role": "Backend Developer",
                "company": "Acme",
                "period": "2022 – 2024",
                "description": "Built APIs.",
            }
        ],
    }

    response = client.put(
        "/freelancers/profile",
        json=payload,
        headers=_headers(registered["access_token"]),
    )
    assert response.status_code == 200, response.text

    body = response.json()
    assert body["name"] == "Aarav S. Sharma"
    assert body["headline"] == "Senior Python developer"
    assert body["location"] == "Bengaluru, India"
    assert body["availability"] == "Part-time only"
    assert body["years_experience"] == 5
    assert body["experience_level"] == "Expert"
    assert body["hourly_rate"] == 45.5
    assert body["currency"] == "INR"
    assert body["skills"] == ["Python", "FastAPI", "MongoDB"]
    assert body["summary"] == "I design reliable APIs."
    assert body["portfolio"][0]["title"] == "Payments API"
    assert body["portfolio"][0]["technologies"] == ["FastAPI", "MongoDB"]
    assert body["work_history"][0]["role"] == "Backend Developer"
    assert body["work_history"][0]["description"] == "Built APIs."

    user = domain_db.users.find_one({"_id": ObjectId(body["id"])})
    assert user["name"] == "Aarav S. Sharma"
    assert user["headline"] == "Senior Python developer"
    assert user["years_experience"] == 5


def test_update_profile_can_clear_optional_fields(client, domain_db):
    registered = _register_freelancer(client)
    token = registered["access_token"]

    first = client.put(
        "/freelancers/profile",
        json={
            "summary": "Temporary summary",
            "hourly_rate": 20,
            "skills": ["Python"],
            "portfolio": [{"title": "Temporary project"}],
            "work_history": [{"role": "Temporary role"}],
            "location": "Temporary location",
            "avatar_url": "https://example.com/avatar.png",
        },
        headers=_headers(token),
    )
    assert first.status_code == 200, first.text

    cleared = client.put(
        "/freelancers/profile",
        json={
            "summary": None,
            "hourly_rate": None,
            "skills": None,
            "portfolio": None,
            "work_history": None,
            "location": None,
            "avatar_url": None,
        },
        headers=_headers(token),
    )
    assert cleared.status_code == 200, cleared.text

    body = cleared.json()
    assert body["summary"] == ""
    assert body["hourly_rate"] is None
    assert body["skills"] == []
    assert body["portfolio"] == []
    assert body["work_history"] == []
    assert body["location"] == ""
    assert body["avatar_url"] is None


@pytest.mark.parametrize(
    "field",
    [
        "name",
        "headline",
        "availability",
        "years_experience",
        "experience_level",
        "currency",
    ],
)
def test_update_profile_rejects_null_for_required_fields(
    client, domain_db, field
):
    registered = _register_freelancer(client)
    response = client.put(
        "/freelancers/profile",
        json={field: None},
        headers=_headers(registered["access_token"]),
    )
    assert response.status_code == 422
    assert "cannot be null" in response.text


@pytest.mark.parametrize(
    "payload,field",
    [
        ({"availability": "Whenever"}, "availability"),
        ({"experience_level": "Senior"}, "experience_level"),
        ({"years_experience": -1}, "years_experience"),
        ({"hourly_rate": 0}, "hourly_rate"),
        ({"currency": "US"}, "currency"),
        (
            {
                "portfolio": [
                    {"title": "Unsafe link", "url": "javascript:alert(1)"}
                ]
            },
            "portfolio",
        ),
        ({"work_history": [{"role": ""}]}, "work_history"),
    ],
)
def test_update_profile_rejects_invalid_values(client, domain_db, payload, field):
    registered = _register_freelancer(client)
    response = client.put(
        "/freelancers/profile",
        json=payload,
        headers=_headers(registered["access_token"]),
    )
    assert response.status_code == 422
    assert any(
        field in str(error.get("loc", []))
        for error in response.json()["detail"]
    )


def test_update_profile_preserves_fields_not_in_the_edit_form(
    client, domain_db
):
    registered = _register_freelancer(client)
    user_id = ObjectId(registered["user"]["id"])
    domain_db.freelancers.update_one(
        {"_id": user_id},
        {
            "$set": {
                "portfolio": [
                    {
                        "title": "Payments API",
                        "description": "Old description",
                        "url": "https://example.com",
                        "technologies": ["FastAPI"],
                    }
                ],
                "work_history": [
                    {
                        "role": "Backend Developer",
                        "company": "Acme",
                        "period": "2022 – 2024",
                        "description": "Built APIs.",
                    }
                ],
            }
        },
    )

    response = client.put(
        "/freelancers/profile",
        json={
            "portfolio": [
                {
                    "title": "Payments API",
                    "description": "New description",
                    "url": "https://example.com",
                }
            ],
            "work_history": [
                {
                    "role": "Backend Developer",
                    "company": "Acme",
                    "period": "2022 – 2024",
                }
            ],
        },
        headers=_headers(registered["access_token"]),
    )
    assert response.status_code == 200, response.text

    body = response.json()
    assert body["portfolio"][0]["description"] == "New description"
    assert body["portfolio"][0]["technologies"] == ["FastAPI"]
    assert body["work_history"][0]["description"] == "Built APIs."


def test_update_profile_response_never_leaks_private_fields(client, domain_db):
    registered = _register_freelancer(client)
    response = client.put(
        "/freelancers/profile",
        json={"summary": "Hello"},
        headers=_headers(registered["access_token"]),
    )
    assert response.status_code == 200
    assert "password_hash" not in response.text
    assert FREELANCER["email"] not in response.text


# ---------------------------------------------------------------------------
# Listing and filtering
# ---------------------------------------------------------------------------


def test_list_freelancers_sorts_by_rating(client, domain_db):
    profiles = [
        ("a@example.com", "Alpha", 4.2, 3),
        ("b@example.com", "Beta", 4.9, 10),
        ("c@example.com", "Gamma", 4.5, 5),
    ]
    for email, name, rating, reviews in profiles:
        registered = _register_freelancer(client, email=email, name=name)
        domain_db.freelancers.update_one(
            {"_id": ObjectId(registered["user"]["id"])},
            {"$set": {"avg_rating": rating, "reviews_count": reviews}},
        )

    response = client.get(
        "/freelancers", params={"limit": 2, "sort": "rating"}
    )
    assert response.status_code == 200

    body = response.json()
    assert body["total"] == 3
    assert [item["name"] for item in body["items"]] == ["Beta", "Gamma"]
    assert all("email" not in item for item in body["items"])


def test_list_freelancers_filters_by_skill_case_insensitively(
    client, domain_db
):
    python_profile = _register_freelancer(
        client, email="python@example.com", name="Python Dev"
    )
    js_profile = _register_freelancer(
        client, email="js@example.com", name="JS Dev"
    )
    domain_db.freelancers.update_one(
        {"_id": ObjectId(python_profile["user"]["id"])},
        {"$set": {"skills": ["Python", "FastAPI"]}},
    )
    domain_db.freelancers.update_one(
        {"_id": ObjectId(js_profile["user"]["id"])},
        {"$set": {"skills": ["JavaScript"]}},
    )

    response = client.get("/freelancers", params={"skills": "python"})
    assert response.status_code == 200

    body = response.json()
    assert body["total"] == 1
    assert body["items"][0]["id"] == python_profile["user"]["id"]


def test_list_freelancers_searches_name_headline_and_skills(client, domain_db):
    match = _register_freelancer(
        client,
        email="match@example.com",
        name="Alice",
        headline="FastAPI specialist",
    )
    _register_freelancer(
        client,
        email="other@example.com",
        name="Bob",
        headline="Frontend developer",
    )

    response = client.get("/freelancers", params={"q": "fastapi"})
    assert response.status_code == 200

    body = response.json()
    assert body["total"] == 1
    assert body["items"][0]["id"] == match["user"]["id"]


@pytest.mark.parametrize("limit", [0, 101])
def test_list_freelancers_rejects_invalid_limit(client, domain_db, limit):
    response = client.get("/freelancers", params={"limit": limit})
    assert response.status_code == 422


def test_list_freelancers_rejects_unknown_sort(client, domain_db):
    response = client.get("/freelancers", params={"sort": "name"})
    assert response.status_code == 422
