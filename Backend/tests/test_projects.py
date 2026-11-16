"""Phase 3 client project tests.

All tests use the shared in-memory ``domain_db`` fixture, so the suite never
contacts MongoDB Atlas.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

import pytest
from bson import ObjectId

CLIENT = {
    "name": "Priya Nair",
    "email": "priya@example.com",
    "password": "Passw0rd1",
    "role": "client",
    "company_name": "Northwind Logistics",
}

FREELANCER = {
    "name": "Aarav Sharma",
    "email": "aarav@example.com",
    "password": "Passw0rd1",
    "role": "freelancer",
    "headline": "Full-stack developer",
    "years_experience": 3,
}

FUTURE_DEADLINE = date.today() + timedelta(days=30)

FRONTEND_CATEGORIES = [
    "Web Development",
    "Mobile App Development",
    "AI & Generative AI",
    "Machine Learning & Deep Learning",
    "Data Science & Analytics",
    "Cybersecurity",
    "Cloud Computing",
    "Backend Development & APIs",
    "Frontend Development",
    "Full Stack Development",
    "DevOps & Cloud Engineering",
    "UI/UX Design",
    "Software Testing & QA",
    "Blockchain & Web3",
    "Game Development",
    "Database Management",
    "Embedded Systems & IoT",
    "Networking & IT Support",
    "Automation & RPA",
    "Content Writing & Copywriting",
    "Digital Marketing & SEO",
    "Graphic Design",
    "Video Editing & Animation",
    "Business & Consulting",
    "Other",
]


def _headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _register_client(
    client,
    *,
    email: str = "priya@example.com",
    name: str = "Priya Nair",
    company_name: str = "Northwind Logistics",
):
    payload = {
        **CLIENT,
        "email": email,
        "name": name,
        "company_name": company_name,
    }
    response = client.post("/auth/register", json=payload)
    assert response.status_code == 201, response.text
    return response.json()


def _register_freelancer(client):
    response = client.post("/auth/register", json=FREELANCER)
    assert response.status_code == 201, response.text
    return response.json()


def _project_payload(**overrides):
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
        "deadline": FUTURE_DEADLINE.isoformat(),
        "duration": "6 weeks",
        "requirements": ["Design the API", "Write automated tests"],
    }
    payload.update(overrides)
    return payload


def _insert_project(
    domain_db,
    *,
    client_id: ObjectId,
    status: str = "open",
    created_at: datetime | None = None,
    deadline: datetime | None = None,
    title: str = "Project",
) -> ObjectId:
    """Insert a project directly for deterministic list/sort tests."""
    now = datetime.now(timezone.utc)
    project_id = ObjectId()
    domain_db.projects.insert_one(
        {
            "_id": project_id,
            "title": title,
            "description": "x" * 100,
            "category": "Backend & APIs",
            "skills": ["Python"],
            "experience_level": "Intermediate",
            "budget_type": "fixed",
            "budget_min": 100,
            "budget_max": 200,
            "currency": "USD",
            "deadline": deadline or (now + timedelta(days=10)),
            "duration": "2 weeks",
            "status": status,
            "client_id": client_id,
            "client_name": "Test Client",
            "location": "",
            "requirements": [],
            "deliverables": [],
            "created_at": created_at or now,
            "updated_at": now,
        }
    )
    return project_id


# ---------------------------------------------------------------------------
# Creating projects
# ---------------------------------------------------------------------------


def test_create_project_requires_authentication(client, domain_db):
    response = client.post("/projects", json=_project_payload())
    assert response.status_code == 401
    assert response.headers.get("www-authenticate") == "Bearer"
    assert response.json()["detail"] == "Authentication required."


def test_create_project_requires_client_role(client, domain_db):
    registered = _register_freelancer(client)
    response = client.post(
        "/projects",
        json=_project_payload(),
        headers=_headers(registered["access_token"]),
    )
    assert response.status_code == 403
    assert (
        response.json()["detail"]
        == "You do not have permission to perform this action."
    )


def test_create_project_success(client, domain_db):
    registered = _register_client(client)

    response = client.post(
        "/projects",
        json=_project_payload(),
        headers=_headers(registered["access_token"]),
    )
    assert response.status_code == 201, response.text

    body = response.json()
    assert body["id"]
    assert body["title"] == "Build a REST API for logistics"
    assert body["category"] == "Backend & APIs"
    assert body["skills"] == ["Python", "FastAPI", "MongoDB"]
    assert body["budget_min"] == 1200
    assert body["budget_max"] == 2000
    assert body["currency"] == "USD"
    assert body["budget_type"] == "fixed"
    assert body["deadline"] == FUTURE_DEADLINE.isoformat()
    assert body["duration"] == "6 weeks"
    assert body["experience_level"] == "Intermediate"
    assert body["status"] == "open"
    assert body["client_id"] == registered["user"]["id"]
    assert body["client_name"] == "Northwind Logistics"
    assert body["location"] == ""
    assert body["requirements"] == [
        "Design the API",
        "Write automated tests",
    ]
    assert body["deliverables"] == []
    assert body["applications_count"] == 0
    assert body["created_at"]
    assert body["updated_at"]

    stored = domain_db.projects.find_one({"_id": ObjectId(body["id"])})
    assert stored is not None
    assert stored["client_id"] == ObjectId(registered["user"]["id"])
    assert stored["category"] == "Backend & APIs"
    assert stored["status"] == "open"
    assert isinstance(stored["deadline"], datetime)
    assert stored["created_at"] is not None


def test_create_project_accepts_and_stores_all_frontend_categories(
    client, domain_db
):
    registered = _register_client(client)
    created_categories = []

    for index, category in enumerate(FRONTEND_CATEGORIES, start=1):
        response = client.post(
            "/projects",
            json=_project_payload(
                title=f"Category coverage project {index}",
                category=category,
            ),
            headers=_headers(registered["access_token"]),
        )
        assert response.status_code == 201, (category, response.text)

        body = response.json()
        assert body["category"] == category
        stored = domain_db.projects.find_one({"_id": ObjectId(body["id"])})
        assert stored is not None
        assert stored["category"] == category
        created_categories.append(body["category"])

    assert created_categories == FRONTEND_CATEGORIES

    listing = client.get("/projects", params={"limit": 100})
    assert listing.status_code == 200
    assert {item["category"] for item in listing.json()["items"]} == set(
        FRONTEND_CATEGORIES
    )


def test_create_project_uses_name_when_company_is_missing(client, domain_db):
    registered = _register_client(client)
    domain_db.users.update_one(
        {"_id": ObjectId(registered["user"]["id"])},
        {"$set": {"company_name": None}},
    )

    response = client.post(
        "/projects",
        json=_project_payload(),
        headers=_headers(registered["access_token"]),
    )
    assert response.status_code == 201, response.text
    assert response.json()["client_name"] == "Priya Nair"


def test_create_project_normalizes_skills_and_currency(client, domain_db):
    registered = _register_client(client)
    payload = _project_payload(
        skills=[" Python ", "python", "FastAPI", ""],
        currency="usd",
    )

    response = client.post(
        "/projects",
        json=payload,
        headers=_headers(registered["access_token"]),
    )
    assert response.status_code == 201, response.text

    body = response.json()
    assert body["skills"] == ["Python", "FastAPI"]
    assert body["currency"] == "USD"


@pytest.mark.parametrize(
    "payload,field",
    [
        (dict(_project_payload(), title="Short"), "title"),
        (dict(_project_payload(), description="Too short."), "description"),
        (
            {
                key: value
                for key, value in _project_payload().items()
                if key != "category"
            },
            "category",
        ),
        (dict(_project_payload(), skills=[]), "skills"),
        (
            dict(
                _project_payload(),
                skills=[f"Skill {index}" for index in range(13)],
            ),
            "skills",
        ),
        (dict(_project_payload(), experience_level="Senior"), "experience_level"),
        (dict(_project_payload(), budget_type="weekly"), "budget_type"),
        (dict(_project_payload(), budget_min=5000, budget_max=1000), "budget"),
        (dict(_project_payload(), currency="US"), "currency"),
        (
            dict(
                _project_payload(),
                deadline=(date.today() - timedelta(days=1)).isoformat(),
            ),
            "deadline",
        ),
        (dict(_project_payload(), deadline="not-a-date"), "deadline"),
    ],
)
def test_create_project_rejects_invalid_payload(
    client, domain_db, payload, field
):
    registered = _register_client(client)
    response = client.post(
        "/projects",
        json=payload,
        headers=_headers(registered["access_token"]),
    )
    assert response.status_code == 422
    if field == "budget":
        assert "Maximum budget" in response.text
    else:
        assert any(
            field in str(error.get("loc", []))
            for error in response.json()["detail"]
        )


def test_project_response_never_leaks_private_fields(client, domain_db):
    registered = _register_client(client)
    response = client.post(
        "/projects",
        json=_project_payload(),
        headers=_headers(registered["access_token"]),
    )
    assert response.status_code == 201
    assert "password_hash" not in response.text
    assert CLIENT["email"] not in response.text


# ---------------------------------------------------------------------------
# Reading and filtering projects
# ---------------------------------------------------------------------------


def test_list_projects_defaults_to_open(client, domain_db):
    registered = _register_client(client)
    client_id = ObjectId(registered["user"]["id"])

    created = client.post(
        "/projects",
        json=_project_payload(),
        headers=_headers(registered["access_token"]),
    )
    assert created.status_code == 201
    open_id = created.json()["id"]

    _insert_project(domain_db, client_id=client_id, status="closed")

    response = client.get("/projects")
    assert response.status_code == 200

    body = response.json()
    assert body["total"] == 1
    assert [item["id"] for item in body["items"]] == [open_id]


def test_list_projects_filters_by_status(client, domain_db):
    registered = _register_client(client)
    client_id = ObjectId(registered["user"]["id"])
    _insert_project(domain_db, client_id=client_id, status="open")
    closed_id = _insert_project(domain_db, client_id=client_id, status="closed")

    response = client.get("/projects", params={"status": "closed"})
    assert response.status_code == 200

    body = response.json()
    assert body["total"] == 1
    assert body["items"][0]["id"] == str(closed_id)


def test_list_my_projects_requires_authentication(client, domain_db):
    response = client.get("/projects", params={"mine": "true"})
    assert response.status_code == 401
    assert response.headers.get("www-authenticate") == "Bearer"
    assert response.json()["detail"] == "Authentication required."


def test_list_my_projects_requires_client_role(client, domain_db):
    registered = _register_freelancer(client)
    response = client.get(
        "/projects",
        params={"mine": "true"},
        headers=_headers(registered["access_token"]),
    )
    assert response.status_code == 403


def test_list_my_projects_returns_only_own_projects(client, domain_db):
    first = _register_client(
        client,
        email="first@example.com",
        name="First Client",
        company_name="First Co",
    )
    second = _register_client(
        client,
        email="second@example.com",
        name="Second Client",
        company_name="Second Co",
    )
    first_id = ObjectId(first["user"]["id"])
    second_id = ObjectId(second["user"]["id"])

    first_open = _insert_project(domain_db, client_id=first_id, status="open")
    first_closed = _insert_project(
        domain_db, client_id=first_id, status="closed"
    )
    _insert_project(domain_db, client_id=second_id, status="open")

    response = client.get(
        "/projects",
        params={"mine": "true"},
        headers=_headers(first["access_token"]),
    )
    assert response.status_code == 200

    body = response.json()
    assert body["total"] == 2
    assert {item["id"] for item in body["items"]} == {
        str(first_open),
        str(first_closed),
    }


def test_list_projects_limit_and_recent_sort(client, domain_db):
    registered = _register_client(client)
    client_id = ObjectId(registered["user"]["id"])
    now = datetime.now(timezone.utc)

    _insert_project(
        domain_db,
        client_id=client_id,
        created_at=now - timedelta(days=2),
        title="Oldest",
    )
    middle = _insert_project(
        domain_db,
        client_id=client_id,
        created_at=now - timedelta(days=1),
        title="Middle",
    )
    newest = _insert_project(
        domain_db, client_id=client_id, created_at=now, title="Newest"
    )

    response = client.get("/projects", params={"limit": 2})
    assert response.status_code == 200

    body = response.json()
    assert body["total"] == 3
    assert [item["id"] for item in body["items"]] == [
        str(newest),
        str(middle),
    ]


def test_list_projects_can_sort_by_deadline(client, domain_db):
    registered = _register_client(client)
    client_id = ObjectId(registered["user"]["id"])
    now = datetime.now(timezone.utc)

    later = _insert_project(
        domain_db,
        client_id=client_id,
        deadline=now + timedelta(days=20),
        title="Later",
    )
    sooner = _insert_project(
        domain_db,
        client_id=client_id,
        deadline=now + timedelta(days=5),
        title="Sooner",
    )

    response = client.get("/projects", params={"sort": "deadline"})
    assert response.status_code == 200
    assert [item["id"] for item in response.json()["items"]] == [
        str(sooner),
        str(later),
    ]


@pytest.mark.parametrize("limit", [0, 101])
def test_list_projects_rejects_invalid_limit(client, domain_db, limit):
    response = client.get("/projects", params={"limit": limit})
    assert response.status_code == 422


def test_list_projects_rejects_unknown_sort(client, domain_db):
    response = client.get("/projects", params={"sort": "budget"})
    assert response.status_code == 422


def test_list_projects_rejects_unknown_status(client, domain_db):
    response = client.get("/projects", params={"status": "archived"})
    assert response.status_code == 422


def test_get_project_success(client, domain_db):
    registered = _register_client(client)
    created = client.post(
        "/projects",
        json=_project_payload(),
        headers=_headers(registered["access_token"]),
    )
    assert created.status_code == 201
    project_id = created.json()["id"]

    response = client.get(f"/projects/{project_id}")
    assert response.status_code == 200

    body = response.json()
    assert body["id"] == project_id
    assert body["title"] == "Build a REST API for logistics"
    assert body["client_id"] == registered["user"]["id"]
    assert body["client_name"] == "Northwind Logistics"
    assert body["applications_count"] == 0


@pytest.mark.parametrize(
    "project_id",
    [str(ObjectId()), "not-an-object-id"],
)
def test_get_project_unknown_returns_404(client, domain_db, project_id):
    response = client.get(f"/projects/{project_id}")
    assert response.status_code == 404
    assert response.json()["detail"] == "Project not found."


def test_project_application_counts_are_included(client, domain_db):
    registered = _register_client(client)
    created = client.post(
        "/projects",
        json=_project_payload(),
        headers=_headers(registered["access_token"]),
    )
    assert created.status_code == 201
    project_id = ObjectId(created.json()["id"])

    domain_db.applications.insert_many(
        [
            {
                "project_id": project_id,
                "freelancer_id": ObjectId(),
                "status": "pending",
            },
            {
                "project_id": project_id,
                "freelancer_id": ObjectId(),
                "status": "shortlisted",
            },
            {
                "project_id": ObjectId(),
                "freelancer_id": ObjectId(),
                "status": "pending",
            },
        ]
    )

    detail = client.get(f"/projects/{project_id}")
    assert detail.status_code == 200
    assert detail.json()["applications_count"] == 2

    listing = client.get("/projects")
    assert listing.status_code == 200
    item = next(
        item
        for item in listing.json()["items"]
        if item["id"] == str(project_id)
    )
    assert item["applications_count"] == 2
