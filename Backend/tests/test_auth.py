"""Phase 2 authentication tests.

Every test uses mongomock, so the suite never contacts MongoDB Atlas.
The shared ``client`` fixture also fakes the startup health ping.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import jwt
import mongomock
import pytest
from bson import ObjectId
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from Backend.config import get_settings
from Backend.dependencies import require_role
from Backend.utils.security import hash_password, verify_password

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


@pytest.fixture
def fake_db(monkeypatch):
    """Replace the service's database handle with an in-memory mock."""
    db = mongomock.MongoClient().freelancer_platform
    db.users.create_index("email", unique=True)
    monkeypatch.setattr("Backend.services.auth_service.get_database", lambda: db)
    return db


def _headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _register(client: TestClient, payload: dict):
    return client.post("/auth/register", json=payload)


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------


def test_register_freelancer_success(client, fake_db):
    response = _register(client, FREELANCER)
    assert response.status_code == 201

    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["access_token"]

    user = body["user"]
    assert user["role"] == "freelancer"
    assert user["email"] == "aarav@example.com"
    assert user["headline"] == "Full-stack developer"
    assert user["years_experience"] == 3
    assert user["id"]

    stored = fake_db.users.find_one({"email": "aarav@example.com"})
    assert stored is not None
    assert stored["password_hash"] != FREELANCER["password"]
    assert stored["password_hash"].startswith("$2")

    profile = fake_db.freelancers.find_one({"_id": ObjectId(user["id"])})
    assert profile is not None
    assert profile["headline"] == "Full-stack developer"
    assert profile["experience_level"] == "Intermediate"


def test_register_client_success(client, fake_db):
    response = _register(client, CLIENT)
    assert response.status_code == 201

    user = response.json()["user"]
    assert user["role"] == "client"
    assert user["company_name"] == "Northwind Logistics"

    profile = fake_db.clients.find_one({"_id": ObjectId(user["id"])})
    assert profile is not None
    assert profile["company_name"] == "Northwind Logistics"


def test_register_duplicate_email_returns_409(client, fake_db):
    assert _register(client, FREELANCER).status_code == 201

    duplicate = dict(FREELANCER, email="AARAV@Example.com")
    response = _register(client, duplicate)

    assert response.status_code == 409
    assert "already exists" in response.json()["detail"].lower()
    assert fake_db.users.count_documents({}) == 1


def test_register_invalid_email_returns_422(client, fake_db):
    response = _register(client, dict(FREELANCER, email="not-an-email"))
    assert response.status_code == 422
    assert any(error["loc"][-1] == "email" for error in response.json()["detail"])


@pytest.mark.parametrize("password", ["short", "onlyletters", "12345678"])
def test_register_weak_password_returns_422(client, fake_db, password):
    response = _register(client, dict(FREELANCER, password=password))
    assert response.status_code == 422
    assert any(error["loc"][-1] == "password" for error in response.json()["detail"])


@pytest.mark.parametrize(
    "payload,field",
    [
        ({k: v for k, v in FREELANCER.items() if k != "headline"}, "headline"),
        ({k: v for k, v in FREELANCER.items() if k != "years_experience"}, "years_experience"),
        ({k: v for k, v in CLIENT.items() if k != "company_name"}, "company_name"),
    ],
)
def test_register_requires_role_specific_fields(client, fake_db, payload, field):
    response = _register(client, payload)
    assert response.status_code == 422
    assert any(error["loc"][-1] == field for error in response.json()["detail"])


def test_register_confirm_password_mismatch_returns_422(client, fake_db):
    response = _register(client, dict(FREELANCER, confirm_password="Different1"))
    assert response.status_code == 422
    assert any(
        "Passwords do not match" in error["msg"] for error in response.json()["detail"]
    )


def test_email_is_normalized_before_saving(client, fake_db):
    response = _register(client, dict(FREELANCER, email="  AARAV@Example.COM  "))
    assert response.status_code == 201
    assert response.json()["user"]["email"] == "aarav@example.com"
    assert fake_db.users.find_one({"email": "aarav@example.com"}) is not None


# ---------------------------------------------------------------------------
# Login
# ---------------------------------------------------------------------------


def test_login_success(client, fake_db):
    registered = _register(client, FREELANCER)
    assert registered.status_code == 201

    response = client.post(
        "/auth/login",
        json={"email": "AARAV@EXAMPLE.COM", "password": FREELANCER["password"]},
    )
    assert response.status_code == 200

    body = response.json()
    assert body["access_token"]
    assert body["token_type"] == "bearer"
    assert body["user"]["id"] == registered.json()["user"]["id"]
    assert body["user"]["role"] == "freelancer"


def test_login_incorrect_password_returns_401(client, fake_db):
    _register(client, FREELANCER)
    response = client.post(
        "/auth/login",
        json={"email": FREELANCER["email"], "password": "WrongPass1"},
    )
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid email or password."


def test_login_unknown_email_returns_401(client, fake_db):
    response = client.post(
        "/auth/login",
        json={"email": "nobody@example.com", "password": "Passw0rd1"},
    )
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid email or password."


def test_inactive_user_cannot_login_or_use_token(client, fake_db):
    registered = _register(client, FREELANCER)
    token = registered.json()["access_token"]

    fake_db.users.update_one(
        {"email": FREELANCER["email"]}, {"$set": {"is_active": False}}
    )

    login = client.post(
        "/auth/login",
        json={"email": FREELANCER["email"], "password": FREELANCER["password"]},
    )
    assert login.status_code == 401
    assert login.json()["detail"] == "Invalid email or password."

    me = client.get("/auth/me", headers=_headers(token))
    assert me.status_code == 403
    assert me.json()["detail"] == "This account is inactive."


# ---------------------------------------------------------------------------
# Tokens and protected routes
# ---------------------------------------------------------------------------


def test_protected_route_requires_token(client, fake_db):
    response = client.get("/auth/me")
    assert response.status_code == 401
    assert response.headers.get("www-authenticate") == "Bearer"
    assert response.json()["detail"] == "Authentication required."


def test_invalid_token_returns_401(client, fake_db):
    response = client.get("/auth/me", headers=_headers("not-a-real-token"))
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid or expired token."


def test_expired_token_returns_401(client, fake_db):
    registered = _register(client, FREELANCER)
    user_id = registered.json()["user"]["id"]

    now = datetime.now(timezone.utc)
    payload = {
        "sub": user_id,
        "email": FREELANCER["email"],
        "role": "freelancer",
        "type": "access",
        "iat": now - timedelta(hours=2),
        "exp": now - timedelta(hours=1),
    }
    token = jwt.encode(payload, get_settings().jwt_secret, algorithm="HS256")

    response = client.get("/auth/me", headers=_headers(token))
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid or expired token."


def test_registration_token_can_access_me(client, fake_db):
    registered = _register(client, FREELANCER)
    token = registered.json()["access_token"]

    response = client.get("/auth/me", headers=_headers(token))
    assert response.status_code == 200
    assert response.json()["id"] == registered.json()["user"]["id"]
    assert response.json()["email"] == "aarav@example.com"


# ---------------------------------------------------------------------------
# Role authorization
# ---------------------------------------------------------------------------


def _role_app() -> FastAPI:
    app = FastAPI()

    @app.get("/freelancer-only")
    def freelancer_only(user: dict = Depends(require_role("freelancer"))):
        return {"id": user["id"], "role": user["role"]}

    @app.get("/client-only")
    def client_only(user: dict = Depends(require_role("client"))):
        return {"id": user["id"], "role": user["role"]}

    return app


def test_freelancer_role_authorization(client, fake_db):
    token = _register(client, FREELANCER).json()["access_token"]

    with TestClient(_role_app()) as role_client:
        allowed = role_client.get("/freelancer-only", headers=_headers(token))
        assert allowed.status_code == 200
        assert allowed.json()["role"] == "freelancer"

        denied = role_client.get("/client-only", headers=_headers(token))
        assert denied.status_code == 403
        assert denied.json()["detail"] == "You do not have permission to perform this action."


def test_client_role_authorization(client, fake_db):
    token = _register(client, CLIENT).json()["access_token"]

    with TestClient(_role_app()) as role_client:
        allowed = role_client.get("/client-only", headers=_headers(token))
        assert allowed.status_code == 200
        assert allowed.json()["role"] == "client"

        denied = role_client.get("/freelancer-only", headers=_headers(token))
        assert denied.status_code == 403
        assert denied.json()["detail"] == "You do not have permission to perform this action."


# ---------------------------------------------------------------------------
# Password handling and leak prevention
# ---------------------------------------------------------------------------


def test_password_hash_verification():
    hashed = hash_password("Passw0rd1")
    assert hashed != "Passw0rd1"
    assert hashed.startswith("$2")
    assert verify_password("Passw0rd1", hashed) is True
    assert verify_password("WrongPass1", hashed) is False
    assert verify_password("", hashed) is False


def test_password_hashes_never_appear_in_responses(client, fake_db):
    registered = _register(client, FREELANCER)
    assert registered.status_code == 201

    login = client.post(
        "/auth/login",
        json={"email": FREELANCER["email"], "password": FREELANCER["password"]},
    )
    assert login.status_code == 200

    me = client.get(
        "/auth/me", headers=_headers(registered.json()["access_token"])
    )
    assert me.status_code == 200

    for response in (registered, login, me):
        assert "password_hash" not in response.text
        assert FREELANCER["password"] not in response.text
