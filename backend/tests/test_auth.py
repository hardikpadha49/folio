"""
FolioPulse AI — Auth endpoint tests

Tests:
  - Register a new user
  - Duplicate registration is rejected
  - Login with correct credentials
  - Login with wrong password is rejected
  - Protected /me route requires valid JWT
  - Expired / tampered token is rejected
  - Token refresh works
  - Logout revokes refresh token
  - User A cannot access User B's data
"""
import pytest
from fastapi.testclient import TestClient


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────
VALID_USER = {
    "email": "alice@example.com",
    "full_name": "Alice Smith",
    "password": "SecurePass1",
}

SECOND_USER = {
    "email": "bob@example.com",
    "full_name": "Bob Jones",
    "password": "AnotherPass2",
}


def register_and_login(client: TestClient, user: dict) -> dict:
    """Register a user and return the token response."""
    resp = client.post("/api/v1/auth/register", json=user)
    assert resp.status_code == 201, resp.text
    return resp.json()


def auth_header(access_token: str) -> dict:
    return {"Authorization": f"Bearer {access_token}"}


# ─────────────────────────────────────────────────────────────────────────────
# Registration
# ─────────────────────────────────────────────────────────────────────────────
def test_register_success(client: TestClient):
    resp = client.post("/api/v1/auth/register", json=VALID_USER)
    assert resp.status_code == 201
    data = resp.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["token_type"] == "bearer"
    assert data["expires_in"] > 0


def test_register_duplicate_email(client: TestClient):
    client.post("/api/v1/auth/register", json=VALID_USER)
    resp = client.post("/api/v1/auth/register", json=VALID_USER)
    assert resp.status_code == 409
    assert "already exists" in resp.json()["detail"].lower()


def test_register_weak_password(client: TestClient):
    resp = client.post(
        "/api/v1/auth/register",
        json={**VALID_USER, "password": "weak"},
    )
    assert resp.status_code == 422


def test_register_invalid_email(client: TestClient):
    resp = client.post(
        "/api/v1/auth/register",
        json={**VALID_USER, "email": "not-an-email"},
    )
    assert resp.status_code == 422


# ─────────────────────────────────────────────────────────────────────────────
# Login
# ─────────────────────────────────────────────────────────────────────────────
def test_login_success(client: TestClient):
    client.post("/api/v1/auth/register", json=VALID_USER)
    resp = client.post(
        "/api/v1/auth/login",
        json={"email": VALID_USER["email"], "password": VALID_USER["password"]},
    )
    assert resp.status_code == 200
    assert "access_token" in resp.json()


def test_login_wrong_password(client: TestClient):
    client.post("/api/v1/auth/register", json=VALID_USER)
    resp = client.post(
        "/api/v1/auth/login",
        json={"email": VALID_USER["email"], "password": "wrongpassword"},
    )
    assert resp.status_code == 401


def test_login_nonexistent_user(client: TestClient):
    resp = client.post(
        "/api/v1/auth/login",
        json={"email": "nobody@example.com", "password": "whatever"},
    )
    assert resp.status_code == 401


# ─────────────────────────────────────────────────────────────────────────────
# Protected route /me
# ─────────────────────────────────────────────────────────────────────────────
def test_me_authenticated(client: TestClient):
    tokens = register_and_login(client, VALID_USER)
    resp = client.get("/api/v1/auth/me", headers=auth_header(tokens["access_token"]))
    assert resp.status_code == 200
    data = resp.json()
    assert data["email"] == VALID_USER["email"]
    assert data["full_name"] == VALID_USER["full_name"]
    assert "hashed_password" not in data


def test_me_no_token(client: TestClient):
    resp = client.get("/api/v1/auth/me")
    assert resp.status_code == 403


def test_me_invalid_token(client: TestClient):
    resp = client.get(
        "/api/v1/auth/me", headers={"Authorization": "Bearer totallyinvalidtoken"}
    )
    assert resp.status_code == 401


def test_me_tampered_token(client: TestClient):
    tokens = register_and_login(client, VALID_USER)
    tampered = tokens["access_token"][:-5] + "XXXXX"
    resp = client.get("/api/v1/auth/me", headers=auth_header(tampered))
    assert resp.status_code == 401


# ─────────────────────────────────────────────────────────────────────────────
# Token refresh
# ─────────────────────────────────────────────────────────────────────────────
def test_refresh_token(client: TestClient):
    tokens = register_and_login(client, VALID_USER)
    resp = client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": tokens["refresh_token"]},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data
    # New access token must be different
    assert data["access_token"] != tokens["access_token"]


def test_refresh_invalid_token(client: TestClient):
    resp = client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": "bogus-token"},
    )
    assert resp.status_code == 401


# ─────────────────────────────────────────────────────────────────────────────
# Logout
# ─────────────────────────────────────────────────────────────────────────────
def test_logout_revokes_refresh_token(client: TestClient):
    tokens = register_and_login(client, VALID_USER)
    # Logout
    resp = client.post(
        "/api/v1/auth/logout",
        json={"refresh_token": tokens["refresh_token"]},
    )
    assert resp.status_code == 204
    # Try to use the revoked refresh token
    resp2 = client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": tokens["refresh_token"]},
    )
    assert resp2.status_code == 401


# ─────────────────────────────────────────────────────────────────────────────
# User isolation
# ─────────────────────────────────────────────────────────────────────────────
def test_user_isolation_portfolios(client: TestClient):
    """User A creates a portfolio; User B cannot see it."""
    tokens_a = register_and_login(client, VALID_USER)
    tokens_b = register_and_login(client, SECOND_USER)

    # A creates a portfolio
    resp = client.post(
        "/api/v1/portfolios",
        json={"name": "Alice's Portfolio"},
        headers=auth_header(tokens_a["access_token"]),
    )
    assert resp.status_code == 201
    portfolio_id = resp.json()["id"]

    # B tries to fetch A's portfolio by ID — must get 404 (not 403, to hide existence)
    resp = client.get(
        f"/api/v1/portfolios/{portfolio_id}",
        headers=auth_header(tokens_b["access_token"]),
    )
    assert resp.status_code == 404

    # B's portfolio list should be empty
    resp = client.get(
        "/api/v1/portfolios",
        headers=auth_header(tokens_b["access_token"]),
    )
    assert resp.status_code == 200
    assert resp.json() == []
