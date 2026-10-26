"""
FolioPulse AI — Live End-to-End Verification Script
Runs against the running FastAPI instance (port 8000) and PostgreSQL database.
Tests all Phase 1 completion gates.
"""
import httpx
import uuid
import sys

BASE_URL = "http://localhost:8000/api/v1"

def run_e2e_verification():
    print("🚀 Starting Phase 1 Live Verification...")
    client = httpx.Client()
    
    # 1. Health check
    r = client.get("http://localhost:8000/health")
    assert r.status_code == 200, f"Health check failed: {r.text}"
    print("✅ 1. System health check: OK")

    # 2. Register Test User 1
    u1_email = f"live_u1_{uuid.uuid4().hex[:6]}@foliopulse.io"
    r = client.post(f"{BASE_URL}/auth/register", json={
        "email": u1_email,
        "full_name": "Live Test User 1",
        "password": "StrongPassword1"
    })
    assert r.status_code == 201, f"User 1 registration failed: {r.text}"
    u1_tokens = r.json()
    assert "access_token" in u1_tokens and "refresh_token" in u1_tokens
    print(f"✅ 2. User 1 registered ({u1_email}): OK")

    # 3. Duplicate registration rejection
    r = client.post(f"{BASE_URL}/auth/register", json={
        "email": u1_email,
        "full_name": "Duplicate User",
        "password": "StrongPassword1"
    })
    assert r.status_code == 409, f"Duplicate registration expected 409, got: {r.status_code}"
    print("✅ 3. Duplicate email rejection: OK (409 Conflict)")

    # 4. User 1 Login
    r = client.post(f"{BASE_URL}/auth/login", json={
        "email": u1_email,
        "password": "StrongPassword1"
    })
    assert r.status_code == 200, f"Login failed: {r.text}"
    u1_auth_header = {"Authorization": f"Bearer {u1_tokens['access_token']}"}
    print("✅ 4. User 1 login and JWT validation: OK")

    # 5. Protected /me route
    r = client.get(f"{BASE_URL}/auth/me", headers=u1_auth_header)
    assert r.status_code == 200, f"/me failed: {r.text}"
    assert r.json()["email"] == u1_email
    print("✅ 5. Protected /me route returned correct identity: OK")

    # 6. Register Test User 2
    u2_email = f"live_u2_{uuid.uuid4().hex[:6]}@foliopulse.io"
    r = client.post(f"{BASE_URL}/auth/register", json={
        "email": u2_email,
        "full_name": "Live Test User 2",
        "password": "StrongPassword2"
    })
    assert r.status_code == 201
    u2_tokens = r.json()
    u2_auth_header = {"Authorization": f"Bearer {u2_tokens['access_token']}"}
    print(f"✅ 6. User 2 registered ({u2_email}): OK")

    # 7. User 1 creates a portfolio
    r = client.post(f"{BASE_URL}/portfolios", json={
        "name": "Live Alpha Fund",
        "description": "Long-term tech and energy",
        "currency": "INR"
    }, headers=u1_auth_header)
    assert r.status_code == 201, f"Portfolio creation failed: {r.text}"
    portfolio_1 = r.json()
    p1_id = portfolio_1["id"]
    print(f"✅ 7. User 1 created portfolio '{portfolio_1['name']}' (ID: {p1_id}): OK")

    # 8. Data Isolation: User 2 tries to access User 1's portfolio (MUST BE 404)
    r = client.get(f"{BASE_URL}/portfolios/{p1_id}", headers=u2_auth_header)
    assert r.status_code == 404, f"Data isolation breached! User 2 received: {r.status_code}"
    print("✅ 8. User isolation verified: User 2 cannot access User 1's portfolio (404 Not Found): OK")

    # 9. User 1 adds holding to portfolio
    r = client.post(f"{BASE_URL}/portfolios/{p1_id}/holdings", json={
        "ticker": "TCS.NS",
        "name": "Tata Consultancy Services",
        "quantity": 25.0,
        "average_cost": 3850.50,
        "asset_class": "equity",
        "sector": "Information Technology"
    }, headers=u1_auth_header)
    assert r.status_code == 201, f"Add holding failed: {r.text}"
    holding = r.json()
    assert holding["ticker"] == "TCS.NS"
    assert holding["invested_value"] == 25.0 * 3850.50
    print(f"✅ 9. Added holding '{holding['ticker']}' with invested value ₹{holding['invested_value']:,}: OK")

    # 10. User 2's portfolio list remains empty
    r = client.get(f"{BASE_URL}/portfolios", headers=u2_auth_header)
    assert r.status_code == 200 and len(r.json()) == 0, "User 2 portfolio list leaked data!"
    print("✅ 10. User 2 portfolio list is clean (0 portfolios): OK")

    # 11. Refresh token exchange
    r = client.post(f"{BASE_URL}/auth/refresh", json={
        "refresh_token": u1_tokens["refresh_token"]
    })
    assert r.status_code == 200, f"Refresh failed: {r.text}"
    new_access_token = r.json()["access_token"]
    assert new_access_token != u1_tokens["access_token"]
    print("✅ 11. Refresh token rotation succeeded: OK")

    print("\n🎉 ALL PHASE 1 LIVE INTEGRATION TESTS PASSED WITH 100% SUCCESS!")

if __name__ == "__main__":
    run_e2e_verification()
