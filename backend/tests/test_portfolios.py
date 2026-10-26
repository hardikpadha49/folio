"""
FolioPulse AI — Portfolio and Holdings endpoint tests
"""
import pytest
from fastapi.testclient import TestClient


USER_A = {"email": "alice@test.com", "full_name": "Alice", "password": "TestPass1"}
USER_B = {"email": "bob@test.com",   "full_name": "Bob",   "password": "TestPass2"}


def register(client, user):
    r = client.post("/api/v1/auth/register", json=user)
    assert r.status_code == 201
    return r.json()["access_token"]


def h(token):
    return {"Authorization": f"Bearer {token}"}


# ─────────────────────────────────────────────────────────────────────────────
# Portfolio CRUD
# ─────────────────────────────────────────────────────────────────────────────
def test_create_portfolio(client: TestClient):
    token = register(client, USER_A)
    resp = client.post(
        "/api/v1/portfolios",
        json={"name": "My Portfolio", "currency": "INR"},
        headers=h(token),
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "My Portfolio"
    assert data["currency"] == "INR"
    assert data["holding_count"] == 0


def test_duplicate_portfolio_name_rejected(client: TestClient):
    token = register(client, USER_A)
    client.post("/api/v1/portfolios", json={"name": "P1"}, headers=h(token))
    resp = client.post("/api/v1/portfolios", json={"name": "P1"}, headers=h(token))
    assert resp.status_code == 409


def test_list_portfolios_empty(client: TestClient):
    token = register(client, USER_A)
    resp = client.get("/api/v1/portfolios", headers=h(token))
    assert resp.status_code == 200
    assert resp.json() == []


def test_list_portfolios_shows_own(client: TestClient):
    token = register(client, USER_A)
    client.post("/api/v1/portfolios", json={"name": "P1"}, headers=h(token))
    client.post("/api/v1/portfolios", json={"name": "P2"}, headers=h(token))
    resp = client.get("/api/v1/portfolios", headers=h(token))
    assert resp.status_code == 200
    assert len(resp.json()) == 2


def test_update_portfolio(client: TestClient):
    token = register(client, USER_A)
    resp = client.post("/api/v1/portfolios", json={"name": "Old"}, headers=h(token))
    pid = resp.json()["id"]
    resp2 = client.patch(
        f"/api/v1/portfolios/{pid}",
        json={"name": "New", "description": "Updated"},
        headers=h(token),
    )
    assert resp2.status_code == 200
    assert resp2.json()["name"] == "New"


def test_delete_portfolio(client: TestClient):
    token = register(client, USER_A)
    resp = client.post("/api/v1/portfolios", json={"name": "ToDelete"}, headers=h(token))
    pid = resp.json()["id"]
    del_resp = client.delete(f"/api/v1/portfolios/{pid}", headers=h(token))
    assert del_resp.status_code == 204
    # Verify it's gone
    get_resp = client.get(f"/api/v1/portfolios/{pid}", headers=h(token))
    assert get_resp.status_code == 404


# ─────────────────────────────────────────────────────────────────────────────
# Holdings CRUD
# ─────────────────────────────────────────────────────────────────────────────
def create_portfolio(client, token, name="Test"):
    r = client.post("/api/v1/portfolios", json={"name": name}, headers=h(token))
    assert r.status_code == 201
    return r.json()["id"]


HOLDING = {
    "ticker": "RELIANCE.NS",
    "name": "Reliance Industries",
    "quantity": 10.0,
    "average_cost": 2500.0,
    "asset_class": "equity",
    "sector": "Energy",
}


def test_add_holding(client: TestClient):
    token = register(client, USER_A)
    pid = create_portfolio(client, token)
    resp = client.post(f"/api/v1/portfolios/{pid}/holdings", json=HOLDING, headers=h(token))
    assert resp.status_code == 201
    data = resp.json()
    assert data["ticker"] == "RELIANCE.NS"
    assert data["invested_value"] == 25000.0


def test_duplicate_holding_rejected(client: TestClient):
    token = register(client, USER_A)
    pid = create_portfolio(client, token)
    client.post(f"/api/v1/portfolios/{pid}/holdings", json=HOLDING, headers=h(token))
    resp = client.post(f"/api/v1/portfolios/{pid}/holdings", json=HOLDING, headers=h(token))
    assert resp.status_code == 409


def test_list_holdings(client: TestClient):
    token = register(client, USER_A)
    pid = create_portfolio(client, token)
    client.post(f"/api/v1/portfolios/{pid}/holdings", json=HOLDING, headers=h(token))
    resp = client.get(f"/api/v1/portfolios/{pid}/holdings", headers=h(token))
    assert resp.status_code == 200
    assert len(resp.json()) == 1


def test_update_holding(client: TestClient):
    token = register(client, USER_A)
    pid = create_portfolio(client, token)
    resp = client.post(f"/api/v1/portfolios/{pid}/holdings", json=HOLDING, headers=h(token))
    hid = resp.json()["id"]
    resp2 = client.patch(
        f"/api/v1/portfolios/{pid}/holdings/{hid}",
        json={"quantity": 20.0, "average_cost": 2600.0},
        headers=h(token),
    )
    assert resp2.status_code == 200
    assert resp2.json()["invested_value"] == 52000.0


def test_delete_holding(client: TestClient):
    token = register(client, USER_A)
    pid = create_portfolio(client, token)
    resp = client.post(f"/api/v1/portfolios/{pid}/holdings", json=HOLDING, headers=h(token))
    hid = resp.json()["id"]
    del_resp = client.delete(f"/api/v1/portfolios/{pid}/holdings/{hid}", headers=h(token))
    assert del_resp.status_code == 204
    list_resp = client.get(f"/api/v1/portfolios/{pid}/holdings", headers=h(token))
    assert list_resp.json() == []


def test_holdings_require_auth(client: TestClient):
    token = register(client, USER_A)
    pid = create_portfolio(client, token)
    resp = client.get(f"/api/v1/portfolios/{pid}/holdings")
    assert resp.status_code == 403


def test_user_b_cannot_add_to_user_a_portfolio(client: TestClient):
    token_a = register(client, USER_A)
    token_b = register(client, USER_B)
    pid = create_portfolio(client, token_a)
    resp = client.post(
        f"/api/v1/portfolios/{pid}/holdings",
        json=HOLDING,
        headers=h(token_b),
    )
    assert resp.status_code == 404  # Existence hidden from other users


def test_invalid_asset_class_rejected(client: TestClient):
    token = register(client, USER_A)
    pid = create_portfolio(client, token)
    resp = client.post(
        f"/api/v1/portfolios/{pid}/holdings",
        json={**HOLDING, "asset_class": "magic"},
        headers=h(token),
    )
    assert resp.status_code == 422


def test_negative_quantity_rejected(client: TestClient):
    token = register(client, USER_A)
    pid = create_portfolio(client, token)
    resp = client.post(
        f"/api/v1/portfolios/{pid}/holdings",
        json={**HOLDING, "quantity": -5.0},
        headers=h(token),
    )
    assert resp.status_code == 422
