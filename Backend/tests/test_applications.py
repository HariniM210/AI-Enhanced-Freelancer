"""Phase 4 application and single-hire workflow tests.

Every test uses the in-memory ``domain_db`` fixture. MongoDB Atlas is never
contacted by this suite.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

import pytest
from bson import ObjectId

COVER_LETTER = (
    "I have built several production FastAPI services with MongoDB and can "
    "deliver this project on time with tests and documentation."
)


def _headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _register_client(
    client,
    *,
    email: str = "priya@example.com",
    name: str = "Priya Nair",
    company_name: str = "Northwind Logistics",
):
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


def _register_freelancer(
    client,
    *,
    email: str = "aarav@example.com",
    name: str = "Aarav Sharma",
    headline: str = "Full-stack developer",
):
    response = client.post(
        "/auth/register",
        json={
            "name": name,
            "email": email,
            "password": "Passw0rd1",
            "role": "freelancer",
            "headline": headline,
            "years_experience": 3,
        },
    )
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
        "deadline": (date.today() + timedelta(days=30)).isoformat(),
        "duration": "6 weeks",
        "requirements": ["Design the API", "Write automated tests"],
    }
    payload.update(overrides)
    return payload


def _create_project(client, client_token: str, **overrides) -> dict:
    response = client.post(
        "/projects",
        json=_project_payload(**overrides),
        headers=_headers(client_token),
    )
    assert response.status_code == 201, response.text
    return response.json()


def _application_payload(project_id: str, **overrides):
    payload = {
        "project_id": project_id,
        "cover_letter": COVER_LETTER,
        "bid_amount": 1500,
        "delivery_days": 21,
    }
    payload.update(overrides)
    return payload


def _apply(client, token: str, project_id: str, **overrides) -> dict:
    response = client.post(
        "/applications",
        json=_application_payload(project_id, **overrides),
        headers=_headers(token),
    )
    assert response.status_code == 201, response.text
    return response.json()


def _set_application_timestamps(
    domain_db, application_id: str, *, created_at: datetime
) -> None:
    domain_db.applications.update_one(
        {"_id": ObjectId(application_id)},
        {"$set": {"created_at": created_at, "updated_at": created_at}},
    )


# ---------------------------------------------------------------------------
# Creating applications
# ---------------------------------------------------------------------------


def test_create_application_requires_authentication(client, domain_db):
    response = client.post(
        "/applications", json=_application_payload(str(ObjectId()))
    )
    assert response.status_code == 401
    assert response.headers.get("www-authenticate") == "Bearer"
    assert response.json()["detail"] == "Authentication required."


def test_create_application_requires_freelancer_role(client, domain_db):
    registered = _register_client(client)
    project = _create_project(client, registered["access_token"])

    response = client.post(
        "/applications",
        json=_application_payload(project["id"]),
        headers=_headers(registered["access_token"]),
    )
    assert response.status_code == 403
    assert (
        response.json()["detail"]
        == "You do not have permission to perform this action."
    )


def test_create_application_success(client, domain_db):
    client_account = _register_client(client)
    freelancer = _register_freelancer(client)
    project = _create_project(client, client_account["access_token"])

    # These fields must be ignored: identity and status are server-managed.
    payload = _application_payload(
        project["id"],
        freelancer_id=str(ObjectId()),
        status="accepted",
    )
    response = client.post(
        "/applications",
        json=payload,
        headers=_headers(freelancer["access_token"]),
    )
    assert response.status_code == 201, response.text

    body = response.json()
    assert body["id"]
    assert body["project_id"] == project["id"]
    assert body["project_title"] == project["title"]
    assert body["project_category"] == project["category"]
    assert body["client_id"] == client_account["user"]["id"]
    assert body["client_name"] == "Northwind Logistics"
    assert body["freelancer_id"] == freelancer["user"]["id"]
    assert body["freelancer_name"] == "Aarav Sharma"
    assert body["freelancer_headline"] == "Full-stack developer"
    assert body["cover_letter"] == COVER_LETTER
    assert body["bid_amount"] == 1500
    assert body["currency"] == "USD"
    assert body["delivery_days"] == 21
    assert body["status"] == "pending"
    assert body["created_at"]
    assert body["updated_at"]
    assert body["project"]["id"] == project["id"]
    assert body["project"]["status"] == "open"
    assert body["freelancer"]["id"] == freelancer["user"]["id"]
    assert body["freelancer"]["name"] == "Aarav Sharma"
    assert body["freelancer"]["skills"] == []

    assert "password_hash" not in response.text
    assert "priya@example.com" not in response.text
    assert "aarav@example.com" not in response.text

    stored = domain_db.applications.find_one({"_id": ObjectId(body["id"])})
    assert stored is not None
    assert stored["status"] == "pending"
    assert stored["freelancer_id"] == ObjectId(freelancer["user"]["id"])
    assert stored["client_id"] == ObjectId(client_account["user"]["id"])
    assert stored["project_id"] == ObjectId(project["id"])


def test_create_application_accepts_proposal_aliases(client, domain_db):
    client_account = _register_client(client)
    freelancer = _register_freelancer(client)
    project = _create_project(client, client_account["access_token"])

    response = client.post(
        "/applications",
        json={
            "project_id": project["id"],
            "proposal": COVER_LETTER,
            "proposed_budget": 1750,
        },
        headers=_headers(freelancer["access_token"]),
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["cover_letter"] == COVER_LETTER
    assert body["bid_amount"] == 1750


@pytest.mark.parametrize(
    "project_id",
    [str(ObjectId()), "not-an-object-id"],
)
def test_create_application_unknown_project_returns_404(
    client, domain_db, project_id
):
    freelancer = _register_freelancer(client)
    response = client.post(
        "/applications",
        json=_application_payload(project_id),
        headers=_headers(freelancer["access_token"]),
    )
    assert response.status_code == 404
    assert response.json()["detail"] == "Project not found."


@pytest.mark.parametrize("project_status", ["in_progress", "completed", "closed"])
def test_create_application_rejects_non_open_project(
    client, domain_db, project_status
):
    client_account = _register_client(client)
    freelancer = _register_freelancer(client)
    project = _create_project(client, client_account["access_token"])
    domain_db.projects.update_one(
        {"_id": ObjectId(project["id"])},
        {"$set": {"status": project_status}},
    )

    response = client.post(
        "/applications",
        json=_application_payload(project["id"]),
        headers=_headers(freelancer["access_token"]),
    )
    assert response.status_code == 409
    assert (
        response.json()["detail"]
        == "This project is no longer accepting applications."
    )


def test_duplicate_application_returns_409_and_does_not_change_count(
    client, domain_db
):
    client_account = _register_client(client)
    freelancer = _register_freelancer(client)
    project = _create_project(client, client_account["access_token"])

    first = _apply(client, freelancer["access_token"], project["id"])
    response = client.post(
        "/applications",
        json=_application_payload(project["id"]),
        headers=_headers(freelancer["access_token"]),
    )
    assert response.status_code == 409
    assert (
        response.json()["detail"]
        == "You have already applied to this project."
    )

    detail = client.get(f"/projects/{project['id']}")
    assert detail.status_code == 200
    assert detail.json()["applications_count"] == 1
    assert domain_db.applications.count_documents({}) == 1
    assert domain_db.applications.count_documents(
        {"_id": ObjectId(first["id"])}
    ) == 1


@pytest.mark.parametrize(
    "overrides,field",
    [
        ({"cover_letter": "Too short."}, "cover_letter"),
        ({"bid_amount": 0}, "bid_amount"),
        ({"bid_amount": -10}, "bid_amount"),
        ({"delivery_days": 0}, "delivery_days"),
        ({"delivery_days": 731}, "delivery_days"),
    ],
)
def test_create_application_rejects_invalid_payload(
    client, domain_db, overrides, field
):
    client_account = _register_client(client)
    freelancer = _register_freelancer(client)
    project = _create_project(client, client_account["access_token"])

    payload = _application_payload(project["id"], **overrides)
    response = client.post(
        "/applications",
        json=payload,
        headers=_headers(freelancer["access_token"]),
    )
    assert response.status_code == 422
    assert any(
        field in str(error.get("loc", []))
        for error in response.json()["detail"]
    )


def test_create_application_requires_a_cover_letter(client, domain_db):
    client_account = _register_client(client)
    freelancer = _register_freelancer(client)
    project = _create_project(client, client_account["access_token"])

    payload = _application_payload(project["id"])
    payload.pop("cover_letter")
    response = client.post(
        "/applications",
        json=payload,
        headers=_headers(freelancer["access_token"]),
    )
    assert response.status_code == 422


# ---------------------------------------------------------------------------
# Listing applications
# ---------------------------------------------------------------------------


def test_list_my_applications_requires_authentication(client, domain_db):
    response = client.get("/applications/my")
    assert response.status_code == 401
    assert response.headers.get("www-authenticate") == "Bearer"
    assert response.json()["detail"] == "Authentication required."


def test_list_my_applications_freelancer_sees_only_own(client, domain_db):
    client_account = _register_client(client)
    first = _register_freelancer(client, email="first@example.com")
    second = _register_freelancer(
        client, email="second@example.com", name="Second Freelancer"
    )
    first_project = _create_project(
        client, client_account["access_token"], title="First project title"
    )
    second_project = _create_project(
        client, client_account["access_token"], title="Second project title"
    )

    first_app = _apply(client, first["access_token"], first_project["id"])
    _apply(client, second["access_token"], second_project["id"])

    response = client.get(
        "/applications/my", headers=_headers(first["access_token"])
    )
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert [item["id"] for item in body["items"]] == [first_app["id"]]
    assert body["items"][0]["freelancer_id"] == first["user"]["id"]


def test_list_my_applications_client_sees_only_received(client, domain_db):
    first_client = _register_client(
        client, email="client1@example.com", name="Client One"
    )
    second_client = _register_client(
        client,
        email="client2@example.com",
        name="Client Two",
        company_name="Second Co",
    )
    freelancer = _register_freelancer(client)
    first_project = _create_project(
        client, first_client["access_token"], title="Client one project"
    )
    second_project = _create_project(
        client, second_client["access_token"], title="Client two project"
    )

    first_app = _apply(client, freelancer["access_token"], first_project["id"])
    _apply(client, freelancer["access_token"], second_project["id"])

    response = client.get(
        "/applications/my", headers=_headers(first_client["access_token"])
    )
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert [item["id"] for item in body["items"]] == [first_app["id"]]
    assert body["items"][0]["client_id"] == first_client["user"]["id"]


def test_list_my_applications_is_newest_first_and_limited(client, domain_db):
    client_account = _register_client(client)
    freelancer = _register_freelancer(client)
    first_project = _create_project(
        client, client_account["access_token"], title="Older project title"
    )
    second_project = _create_project(
        client, client_account["access_token"], title="Newer project title"
    )

    older = _apply(client, freelancer["access_token"], first_project["id"])
    newer = _apply(client, freelancer["access_token"], second_project["id"])
    now = datetime.now(timezone.utc)
    _set_application_timestamps(
        domain_db, older["id"], created_at=now - timedelta(days=2)
    )
    _set_application_timestamps(domain_db, newer["id"], created_at=now)

    response = client.get(
        "/applications/my",
        params={"limit": 1},
        headers=_headers(freelancer["access_token"]),
    )
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 2
    assert [item["id"] for item in body["items"]] == [newer["id"]]


def test_list_project_applications_requires_authentication(client, domain_db):
    response = client.get(f"/projects/{ObjectId()}/applications")
    assert response.status_code == 401


def test_list_project_applications_requires_client_role(client, domain_db):
    freelancer = _register_freelancer(client)
    response = client.get(
        f"/projects/{ObjectId()}/applications",
        headers=_headers(freelancer["access_token"]),
    )
    assert response.status_code == 403


@pytest.mark.parametrize("project_id", [str(ObjectId()), "not-an-object-id"])
def test_list_project_applications_unknown_project_returns_404(
    client, domain_db, project_id
):
    client_account = _register_client(client)
    response = client.get(
        f"/projects/{project_id}/applications",
        headers=_headers(client_account["access_token"]),
    )
    assert response.status_code == 404
    assert response.json()["detail"] == "Project not found."


def test_list_project_applications_rejects_non_owner(client, domain_db):
    owner = _register_client(
        client, email="owner@example.com", name="Owner Client"
    )
    other = _register_client(
        client, email="other@example.com", name="Other Client"
    )
    project = _create_project(client, owner["access_token"])

    response = client.get(
        f"/projects/{project['id']}/applications",
        headers=_headers(other["access_token"]),
    )
    assert response.status_code == 403


def test_list_project_applications_success(client, domain_db):
    client_account = _register_client(client)
    first = _register_freelancer(client, email="first@example.com")
    second = _register_freelancer(
        client, email="second@example.com", name="Second Freelancer"
    )
    project = _create_project(client, client_account["access_token"])
    first_app = _apply(client, first["access_token"], project["id"])
    second_app = _apply(client, second["access_token"], project["id"])

    response = client.get(
        f"/projects/{project['id']}/applications",
        headers=_headers(client_account["access_token"]),
    )
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 2
    assert {item["id"] for item in body["items"]} == {
        first_app["id"],
        second_app["id"],
    }
    assert {item["freelancer_name"] for item in body["items"]} == {
        "Aarav Sharma",
        "Second Freelancer",
    }
    assert all(item["project"]["id"] == project["id"] for item in body["items"])
    assert "password_hash" not in response.text
    assert "first@example.com" not in response.text
    assert "second@example.com" not in response.text


# ---------------------------------------------------------------------------
# Accepting and rejecting applications
# ---------------------------------------------------------------------------


def test_update_status_requires_authentication(client, domain_db):
    response = client.patch(
        f"/applications/{ObjectId()}/status",
        json={"status": "accepted"},
    )
    assert response.status_code == 401


def test_update_status_requires_client_role(client, domain_db):
    freelancer = _register_freelancer(client)
    response = client.patch(
        f"/applications/{ObjectId()}/status",
        json={"status": "accepted"},
        headers=_headers(freelancer["access_token"]),
    )
    assert response.status_code == 403


@pytest.mark.parametrize(
    "application_id", [str(ObjectId()), "not-an-object-id"]
)
def test_update_status_unknown_application_returns_404(
    client, domain_db, application_id
):
    client_account = _register_client(client)
    response = client.patch(
        f"/applications/{application_id}/status",
        json={"status": "accepted"},
        headers=_headers(client_account["access_token"]),
    )
    assert response.status_code == 404
    assert response.json()["detail"] == "Application not found."


def test_update_status_rejects_non_owner(client, domain_db):
    owner = _register_client(
        client, email="owner@example.com", name="Owner Client"
    )
    other = _register_client(
        client, email="other@example.com", name="Other Client"
    )
    freelancer = _register_freelancer(client)
    project = _create_project(client, owner["access_token"])
    application = _apply(client, freelancer["access_token"], project["id"])

    response = client.patch(
        f"/applications/{application['id']}/status",
        json={"status": "rejected"},
        headers=_headers(other["access_token"]),
    )
    assert response.status_code == 403


@pytest.mark.parametrize(
    "invalid_status", ["pending", "shortlist", "withdrawn", "hired", ""]
)
def test_update_status_rejects_invalid_status(
    client, domain_db, invalid_status
):
    client_account = _register_client(client)
    freelancer = _register_freelancer(client)
    project = _create_project(client, client_account["access_token"])
    application = _apply(client, freelancer["access_token"], project["id"])

    response = client.patch(
        f"/applications/{application['id']}/status",
        json={"status": invalid_status},
        headers=_headers(client_account["access_token"]),
    )
    assert response.status_code == 422


def test_accept_application_hires_one_and_rejects_others(client, domain_db):
    client_account = _register_client(client)
    first = _register_freelancer(client, email="first@example.com")
    second = _register_freelancer(
        client, email="second@example.com", name="Second Freelancer"
    )
    project = _create_project(client, client_account["access_token"])
    first_app = _apply(client, first["access_token"], project["id"])
    second_app = _apply(client, second["access_token"], project["id"])

    response = client.patch(
        f"/applications/{first_app['id']}/status",
        json={"status": "accepted"},
        headers=_headers(client_account["access_token"]),
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "accepted"
    assert body["project"]["status"] == "in_progress"
    assert body["updated_at"] >= body["created_at"]

    project_detail = client.get(f"/projects/{project['id']}")
    assert project_detail.status_code == 200
    assert project_detail.json()["status"] == "in_progress"
    assert project_detail.json()["applications_count"] == 2

    stored_project = domain_db.projects.find_one(
        {"_id": ObjectId(project["id"])}
    )
    assert stored_project["status"] == "in_progress"
    assert stored_project["hired_application_id"] == ObjectId(first_app["id"])

    stored_second = domain_db.applications.find_one(
        {"_id": ObjectId(second_app["id"])}
    )
    assert stored_second["status"] == "rejected"

    listing = client.get(
        f"/projects/{project['id']}/applications",
        headers=_headers(client_account["access_token"]),
    )
    assert listing.status_code == 200
    statuses = {item["id"]: item["status"] for item in listing.json()["items"]}
    assert statuses[first_app["id"]] == "accepted"
    assert statuses[second_app["id"]] == "rejected"


def test_shortlist_application_success(client, domain_db):
    client_account = _register_client(client)
    freelancer = _register_freelancer(client)
    project = _create_project(client, client_account["access_token"])
    application = _apply(client, freelancer["access_token"], project["id"])

    response = client.patch(
        f"/applications/{application['id']}/status",
        json={"status": "shortlisted"},
        headers=_headers(client_account["access_token"]),
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "shortlisted"
    assert body["project"]["status"] == "open"

    stored = domain_db.applications.find_one(
        {"_id": ObjectId(application["id"])}
    )
    assert stored["status"] == "shortlisted"
    assert stored["project_snapshot"]["status"] == "open"

    listing = client.get(
        f"/projects/{project['id']}/applications",
        headers=_headers(client_account["access_token"]),
    )
    assert listing.status_code == 200
    assert listing.json()["items"][0]["status"] == "shortlisted"


def test_shortlist_is_idempotent(client, domain_db):
    client_account = _register_client(client)
    freelancer = _register_freelancer(client)
    project = _create_project(client, client_account["access_token"])
    application = _apply(client, freelancer["access_token"], project["id"])

    first = client.patch(
        f"/applications/{application['id']}/status",
        json={"status": "shortlisted"},
        headers=_headers(client_account["access_token"]),
    )
    assert first.status_code == 200
    second = client.patch(
        f"/applications/{application['id']}/status",
        json={"status": "shortlisted"},
        headers=_headers(client_account["access_token"]),
    )
    assert second.status_code == 200
    assert second.json()["status"] == "shortlisted"
    assert domain_db.applications.count_documents({}) == 1


def test_shortlisted_application_can_be_hired(client, domain_db):
    client_account = _register_client(client)
    freelancer = _register_freelancer(client)
    project = _create_project(client, client_account["access_token"])
    application = _apply(client, freelancer["access_token"], project["id"])

    shortlisted = client.patch(
        f"/applications/{application['id']}/status",
        json={"status": "shortlisted"},
        headers=_headers(client_account["access_token"]),
    )
    assert shortlisted.status_code == 200

    accepted = client.patch(
        f"/applications/{application['id']}/status",
        json={"status": "accepted"},
        headers=_headers(client_account["access_token"]),
    )
    assert accepted.status_code == 200, accepted.text
    body = accepted.json()
    assert body["status"] == "accepted"
    assert body["project"]["status"] == "in_progress"

    stored_project = domain_db.projects.find_one(
        {"_id": ObjectId(project["id"])}
    )
    assert stored_project["status"] == "in_progress"
    assert stored_project["hired_application_id"] == ObjectId(
        application["id"]
    )


def test_shortlisted_application_can_be_declined(client, domain_db):
    client_account = _register_client(client)
    freelancer = _register_freelancer(client)
    project = _create_project(client, client_account["access_token"])
    application = _apply(client, freelancer["access_token"], project["id"])

    shortlisted = client.patch(
        f"/applications/{application['id']}/status",
        json={"status": "shortlisted"},
        headers=_headers(client_account["access_token"]),
    )
    assert shortlisted.status_code == 200

    rejected = client.patch(
        f"/applications/{application['id']}/status",
        json={"status": "rejected"},
        headers=_headers(client_account["access_token"]),
    )
    assert rejected.status_code == 200, rejected.text
    assert rejected.json()["status"] == "rejected"

    project_detail = client.get(f"/projects/{project['id']}")
    assert project_detail.json()["status"] == "open"
    stored_project = domain_db.projects.find_one(
        {"_id": ObjectId(project["id"])}
    )
    assert "hired_application_id" not in stored_project


def test_hire_rejects_other_pending_and_shortlisted_applications(
    client, domain_db
):
    client_account = _register_client(client)
    first = _register_freelancer(client, email="first@example.com")
    second = _register_freelancer(
        client, email="second@example.com", name="Second Freelancer"
    )
    third = _register_freelancer(
        client, email="third@example.com", name="Third Freelancer"
    )
    project = _create_project(client, client_account["access_token"])
    first_app = _apply(client, first["access_token"], project["id"])
    second_app = _apply(client, second["access_token"], project["id"])
    third_app = _apply(client, third["access_token"], project["id"])

    shortlisted = client.patch(
        f"/applications/{second_app['id']}/status",
        json={"status": "shortlisted"},
        headers=_headers(client_account["access_token"]),
    )
    assert shortlisted.status_code == 200

    accepted = client.patch(
        f"/applications/{first_app['id']}/status",
        json={"status": "accepted"},
        headers=_headers(client_account["access_token"]),
    )
    assert accepted.status_code == 200, accepted.text

    stored_second = domain_db.applications.find_one(
        {"_id": ObjectId(second_app["id"])}
    )
    stored_third = domain_db.applications.find_one(
        {"_id": ObjectId(third_app["id"])}
    )
    assert stored_second["status"] == "rejected"
    assert stored_third["status"] == "rejected"

    listing = client.get(
        f"/projects/{project['id']}/applications",
        headers=_headers(client_account["access_token"]),
    )
    statuses = {item["id"]: item["status"] for item in listing.json()["items"]}
    assert statuses[first_app["id"]] == "accepted"
    assert statuses[second_app["id"]] == "rejected"
    assert statuses[third_app["id"]] == "rejected"


def test_accepting_a_second_shortlisted_application_returns_409(
    client, domain_db
):
    client_account = _register_client(client)
    first = _register_freelancer(client, email="first@example.com")
    second = _register_freelancer(
        client, email="second@example.com", name="Second Freelancer"
    )
    project = _create_project(client, client_account["access_token"])
    first_app = _apply(client, first["access_token"], project["id"])
    second_app = _apply(client, second["access_token"], project["id"])

    for application in (first_app, second_app):
        response = client.patch(
            f"/applications/{application['id']}/status",
            json={"status": "shortlisted"},
            headers=_headers(client_account["access_token"]),
        )
        assert response.status_code == 200

    accepted = client.patch(
        f"/applications/{first_app['id']}/status",
        json={"status": "accepted"},
        headers=_headers(client_account["access_token"]),
    )
    assert accepted.status_code == 200

    response = client.patch(
        f"/applications/{second_app['id']}/status",
        json={"status": "accepted"},
        headers=_headers(client_account["access_token"]),
    )
    assert response.status_code == 409

    stored_project = domain_db.projects.find_one(
        {"_id": ObjectId(project["id"])}
    )
    assert stored_project["hired_application_id"] == ObjectId(
        first_app["id"]
    )


@pytest.mark.parametrize("final_status", ["accepted", "rejected"])
def test_finalised_application_cannot_be_shortlisted(
    client, domain_db, final_status
):
    client_account = _register_client(client)
    freelancer = _register_freelancer(client)
    project = _create_project(client, client_account["access_token"])
    application = _apply(client, freelancer["access_token"], project["id"])

    finalised = client.patch(
        f"/applications/{application['id']}/status",
        json={"status": final_status},
        headers=_headers(client_account["access_token"]),
    )
    assert finalised.status_code == 200

    response = client.patch(
        f"/applications/{application['id']}/status",
        json={"status": "shortlisted"},
        headers=_headers(client_account["access_token"]),
    )
    assert response.status_code == 409
    assert (
        response.json()["detail"]
        == "This application has already been finalised."
    )


def test_shortlisted_application_cannot_return_to_pending(
    client, domain_db
):
    client_account = _register_client(client)
    freelancer = _register_freelancer(client)
    project = _create_project(client, client_account["access_token"])
    application = _apply(client, freelancer["access_token"], project["id"])

    shortlisted = client.patch(
        f"/applications/{application['id']}/status",
        json={"status": "shortlisted"},
        headers=_headers(client_account["access_token"]),
    )
    assert shortlisted.status_code == 200

    response = client.patch(
        f"/applications/{application['id']}/status",
        json={"status": "pending"},
        headers=_headers(client_account["access_token"]),
    )
    assert response.status_code == 422


def test_accepting_a_second_application_returns_409(client, domain_db):
    client_account = _register_client(client)
    first = _register_freelancer(client, email="first@example.com")
    second = _register_freelancer(
        client, email="second@example.com", name="Second Freelancer"
    )
    project = _create_project(client, client_account["access_token"])
    first_app = _apply(client, first["access_token"], project["id"])
    second_app = _apply(client, second["access_token"], project["id"])

    accepted = client.patch(
        f"/applications/{first_app['id']}/status",
        json={"status": "accepted"},
        headers=_headers(client_account["access_token"]),
    )
    assert accepted.status_code == 200

    response = client.patch(
        f"/applications/{second_app['id']}/status",
        json={"status": "accepted"},
        headers=_headers(client_account["access_token"]),
    )
    assert response.status_code == 409

    stored_project = domain_db.projects.find_one(
        {"_id": ObjectId(project["id"])}
    )
    assert stored_project["hired_application_id"] == ObjectId(first_app["id"])


def test_accept_application_on_closed_project_returns_409(client, domain_db):
    client_account = _register_client(client)
    freelancer = _register_freelancer(client)
    project = _create_project(client, client_account["access_token"])
    application = _apply(client, freelancer["access_token"], project["id"])
    domain_db.projects.update_one(
        {"_id": ObjectId(project["id"])},
        {"$set": {"status": "closed"}},
    )

    response = client.patch(
        f"/applications/{application['id']}/status",
        json={"status": "accepted"},
        headers=_headers(client_account["access_token"]),
    )
    assert response.status_code == 409
    stored = domain_db.applications.find_one(
        {"_id": ObjectId(application["id"])}
    )
    assert stored["status"] == "pending"


def test_reject_application_success(client, domain_db):
    client_account = _register_client(client)
    freelancer = _register_freelancer(client)
    project = _create_project(client, client_account["access_token"])
    application = _apply(client, freelancer["access_token"], project["id"])

    response = client.patch(
        f"/applications/{application['id']}/status",
        json={"status": "rejected"},
        headers=_headers(client_account["access_token"]),
    )
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "rejected"

    project_detail = client.get(f"/projects/{project['id']}")
    assert project_detail.json()["status"] == "open"
    assert project_detail.json()["applications_count"] == 1

    stored_project = domain_db.projects.find_one(
        {"_id": ObjectId(project["id"])}
    )
    assert "hired_application_id" not in stored_project


def test_rejecting_an_accepted_application_returns_409(client, domain_db):
    client_account = _register_client(client)
    freelancer = _register_freelancer(client)
    project = _create_project(client, client_account["access_token"])
    application = _apply(client, freelancer["access_token"], project["id"])

    accepted = client.patch(
        f"/applications/{application['id']}/status",
        json={"status": "accepted"},
        headers=_headers(client_account["access_token"]),
    )
    assert accepted.status_code == 200

    response = client.patch(
        f"/applications/{application['id']}/status",
        json={"status": "rejected"},
        headers=_headers(client_account["access_token"]),
    )
    assert response.status_code == 409
    assert (
        response.json()["detail"]
        == "This application has already been finalised."
    )


def test_repeating_the_same_status_is_idempotent(client, domain_db):
    client_account = _register_client(client)
    freelancer = _register_freelancer(client)
    project = _create_project(client, client_account["access_token"])
    application = _apply(client, freelancer["access_token"], project["id"])

    first = client.patch(
        f"/applications/{application['id']}/status",
        json={"status": "rejected"},
        headers=_headers(client_account["access_token"]),
    )
    assert first.status_code == 200
    second = client.patch(
        f"/applications/{application['id']}/status",
        json={"status": "rejected"},
        headers=_headers(client_account["access_token"]),
    )
    assert second.status_code == 200
    assert second.json()["status"] == "rejected"
    assert domain_db.applications.count_documents({}) == 1


@pytest.mark.parametrize(
    "new_status", ["shortlisted", "accepted", "rejected"]
)
def test_put_status_alias_supports_all_client_actions(
    client, domain_db, new_status
):
    client_account = _register_client(client)
    freelancer = _register_freelancer(client)
    project = _create_project(client, client_account["access_token"])
    application = _apply(client, freelancer["access_token"], project["id"])

    response = client.put(
        f"/applications/{application['id']}/status",
        json={"status": new_status},
        headers=_headers(client_account["access_token"]),
    )
    assert response.status_code == 200, response.text
    assert response.json()["status"] == new_status


def test_application_counts_remain_correct_after_status_changes(
    client, domain_db
):
    client_account = _register_client(client)
    freelancer = _register_freelancer(client)
    project = _create_project(client, client_account["access_token"])

    application = _apply(client, freelancer["access_token"], project["id"])
    assert client.get(f"/projects/{project['id']}").json()[
        "applications_count"
    ] == 1

    rejected = client.patch(
        f"/applications/{application['id']}/status",
        json={"status": "rejected"},
        headers=_headers(client_account["access_token"]),
    )
    assert rejected.status_code == 200
    assert client.get(f"/projects/{project['id']}").json()[
        "applications_count"
    ] == 1
    assert domain_db.applications.count_documents({}) == 1


def _withdraw(client, token: str, application_id: str):
    return client.post(
        f"/applications/{application_id}/withdraw",
        headers=_headers(token),
    )


def test_freelancer_withdraws_pending_application(client, domain_db):
    client_account = _register_client(client)
    freelancer = _register_freelancer(client)
    project = _create_project(client, client_account["access_token"])
    application = _apply(client, freelancer["access_token"], project["id"])

    response = _withdraw(client, freelancer["access_token"], application["id"])
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["id"] == application["id"]
    assert body["status"] == "withdrawn"
    assert body["withdrawn_at"]

    stored = domain_db.applications.find_one({"_id": ObjectId(application["id"])})
    assert stored is not None
    assert stored["status"] == "withdrawn"
    assert isinstance(stored["withdrawn_at"], datetime)
    assert stored["withdrawn_at"].tzinfo is not None
    assert stored["withdrawn_at"].utcoffset().total_seconds() == 0
    assert domain_db.applications.count_documents({}) == 1


def test_freelancer_withdraws_shortlisted_application(client, domain_db):
    client_account = _register_client(client)
    freelancer = _register_freelancer(client)
    project = _create_project(client, client_account["access_token"])
    application = _apply(client, freelancer["access_token"], project["id"])
    shortlisted = client.patch(
        f"/applications/{application['id']}/status",
        json={"status": "shortlisted"},
        headers=_headers(client_account["access_token"]),
    )
    assert shortlisted.status_code == 200

    response = _withdraw(client, freelancer["access_token"], application["id"])
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "withdrawn"
    stored = domain_db.applications.find_one({"_id": ObjectId(application["id"])})
    assert stored["status"] == "withdrawn"
    assert stored["withdrawn_at"] is not None


def test_freelancer_cannot_withdraw_another_users_application(client, domain_db):
    client_account = _register_client(client)
    owner = _register_freelancer(client, email="owner@example.com")
    other = _register_freelancer(
        client, email="other@example.com", name="Other Freelancer"
    )
    project = _create_project(client, client_account["access_token"])
    application = _apply(client, owner["access_token"], project["id"])

    response = _withdraw(client, other["access_token"], application["id"])
    assert response.status_code == 403
    stored = domain_db.applications.find_one({"_id": ObjectId(application["id"])})
    assert stored["status"] == "pending"
    assert stored.get("withdrawn_at") is None


def test_client_cannot_withdraw_an_application(client, domain_db):
    client_account = _register_client(client)
    freelancer = _register_freelancer(client)
    project = _create_project(client, client_account["access_token"])
    application = _apply(client, freelancer["access_token"], project["id"])

    anonymous = client.post(f"/applications/{application['id']}/withdraw")
    assert anonymous.status_code == 401

    response = _withdraw(client, client_account["access_token"], application["id"])
    assert response.status_code == 403
    stored = domain_db.applications.find_one({"_id": ObjectId(application["id"])})
    assert stored["status"] == "pending"


@pytest.mark.parametrize("final_status", ["accepted", "rejected", "completed"])
def test_freelancer_cannot_withdraw_finalised_application(
    client, domain_db, final_status
):
    client_account = _register_client(client)
    freelancer = _register_freelancer(client)
    project = _create_project(client, client_account["access_token"])
    application = _apply(client, freelancer["access_token"], project["id"])

    if final_status == "rejected":
        decided = client.patch(
            f"/applications/{application['id']}/status",
            json={"status": "rejected"},
            headers=_headers(client_account["access_token"]),
        )
        assert decided.status_code == 200
    else:
        hired = client.patch(
            f"/applications/{application['id']}/status",
            json={"status": "accepted"},
            headers=_headers(client_account["access_token"]),
        )
        assert hired.status_code == 200
        if final_status == "completed":
            completed = client.patch(
                f"/applications/{application['id']}/status",
                json={
                    "status": "completed",
                    "rating": 5,
                    "review": "Delivered on time.",
                },
                headers=_headers(client_account["access_token"]),
            )
            assert completed.status_code == 200, completed.text
            assert completed.json()["rating"] == 5
            assert completed.json()["review"] == "Delivered on time."

    response = _withdraw(client, freelancer["access_token"], application["id"])
    assert response.status_code == 409
    stored = domain_db.applications.find_one({"_id": ObjectId(application["id"])})
    assert stored["status"] == final_status
    assert stored.get("withdrawn_at") is None


def test_repeated_withdrawal_is_safe(client, domain_db):
    client_account = _register_client(client)
    freelancer = _register_freelancer(client)
    project = _create_project(client, client_account["access_token"])
    application = _apply(client, freelancer["access_token"], project["id"])

    first = _withdraw(client, freelancer["access_token"], application["id"])
    assert first.status_code == 200, first.text
    second = _withdraw(client, freelancer["access_token"], application["id"])
    assert second.status_code == 200, second.text
    assert second.json()["status"] == "withdrawn"
    assert second.json()["withdrawn_at"] == first.json()["withdrawn_at"]
    assert domain_db.applications.count_documents({"status": "withdrawn"}) == 1


def test_withdrawn_application_stays_in_freelancer_history_only(client, domain_db):
    client_account = _register_client(client)
    freelancer = _register_freelancer(client)
    project = _create_project(client, client_account["access_token"])
    application = _apply(client, freelancer["access_token"], project["id"])
    assert client.get(f"/projects/{project['id']}").json()["applications_count"] == 1

    withdrawn = _withdraw(client, freelancer["access_token"], application["id"])
    assert withdrawn.status_code == 200

    mine = client.get(
        "/applications/my", headers=_headers(freelancer["access_token"])
    )
    assert mine.status_code == 200
    assert [item["id"] for item in mine.json()["items"]] == [application["id"]]
    assert mine.json()["items"][0]["status"] == "withdrawn"
    assert mine.json()["total"] == 1

    client_list = client.get(
        "/applications/my", headers=_headers(client_account["access_token"])
    )
    assert client_list.status_code == 200
    assert client_list.json()["items"] == []
    assert client_list.json()["total"] == 0

    project_list = client.get(
        f"/projects/{project['id']}/applications",
        headers=_headers(client_account["access_token"]),
    )
    assert project_list.status_code == 200
    assert project_list.json()["items"] == []
    assert project_list.json()["total"] == 0
    assert client.get(f"/projects/{project['id']}").json()["applications_count"] == 0
    assert domain_db.applications.count_documents({}) == 1


def test_client_cannot_shortlist_or_hire_withdrawn_application(client, domain_db):
    client_account = _register_client(client)
    freelancer = _register_freelancer(client)
    project = _create_project(client, client_account["access_token"])
    application = _apply(client, freelancer["access_token"], project["id"])
    assert _withdraw(client, freelancer["access_token"], application["id"]).status_code == 200

    for new_status in ("shortlisted", "accepted", "rejected", "completed"):
        response = client.put(
            f"/applications/{application['id']}/status",
            json={"status": new_status},
            headers=_headers(client_account["access_token"]),
        )
        assert response.status_code == 409, response.text
        stored = domain_db.applications.find_one(
            {"_id": ObjectId(application["id"])}
        )
        assert stored["status"] == "withdrawn"

    invalid = client.put(
        f"/applications/{application['id']}/status",
        json={"status": "withdrawn"},
        headers=_headers(client_account["access_token"]),
    )
    assert invalid.status_code == 422


def test_existing_hire_reject_and_completion_still_work(client, domain_db):
    client_account = _register_client(client)
    hired = _register_freelancer(client, email="hired@example.com", name="Hired Dev")
    declined = _register_freelancer(
        client, email="declined@example.com", name="Declined Dev"
    )
    project = _create_project(client, client_account["access_token"])
    other_project = _create_project(
        client, client_account["access_token"], title="Separate open project"
    )
    hired_app = _apply(client, hired["access_token"], project["id"])
    declined_app = _apply(client, declined["access_token"], project["id"])
    withdrawn_app = _apply(client, hired["access_token"], other_project["id"])
    assert _withdraw(
        client, hired["access_token"], withdrawn_app["id"]
    ).status_code == 200

    accepted = client.patch(
        f"/applications/{hired_app['id']}/status",
        json={"status": "accepted"},
        headers=_headers(client_account["access_token"]),
    )
    assert accepted.status_code == 200, accepted.text
    assert accepted.json()["status"] == "accepted"

    stored_declined = domain_db.applications.find_one(
        {"_id": ObjectId(declined_app["id"])}
    )
    assert stored_declined["status"] == "rejected"

    completed = client.patch(
        f"/applications/{hired_app['id']}/status",
        json={"status": "completed", "rating": 4, "review": "Solid delivery."},
        headers=_headers(client_account["access_token"]),
    )
    assert completed.status_code == 200, completed.text
    assert completed.json()["status"] == "completed"
    assert completed.json()["rating"] == 4
    assert completed.json()["review"] == "Solid delivery."
    assert completed.json()["project"]["status"] == "completed"

    stored_withdrawn = domain_db.applications.find_one(
        {"_id": ObjectId(withdrawn_app["id"])}
    )
    assert stored_withdrawn["status"] == "withdrawn"
    assert domain_db.applications.count_documents({}) == 3
