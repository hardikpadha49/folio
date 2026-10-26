"""
FolioPulse AI — Live Phase 2 End-to-End Verification Script
Runs against the active FastAPI instance (port 8000) and live PostgreSQL.
Tests CSV template, preview, commit, and portfolio valuation with user isolation.
"""
import io
import uuid
import httpx

BASE_URL = "http://localhost:8000/api/v1"


def run_phase2_verification():
    print("🚀 Starting Phase 2 Live Verification against running FastAPI & PostgreSQL...")
    client = httpx.Client()

    # 1. Health check
    r = client.get("http://localhost:8000/health")
    assert r.status_code == 200, f"Health check failed: {r.text}"
    print("✅ 1. Health check: OK")

    # 2. Register Test User
    email = f"p2_user_{uuid.uuid4().hex[:6]}@foliopulse.io"
    r = client.post(f"{BASE_URL}/auth/register", json={
        "email": email,
        "full_name": "Phase 2 Investor",
        "password": "StrongPassword1"
    })
    assert r.status_code == 201
    auth_header = {"Authorization": f"Bearer {r.json()['access_token']}"}
    print(f"✅ 2. Registered investor ({email}): OK")

    # 3. Create Portfolio
    r = client.post(f"{BASE_URL}/portfolios", json={
        "name": "Phase 2 Growth",
        "currency": "INR"
    }, headers=auth_header)
    assert r.status_code == 201
    portfolio_id = r.json()["id"]
    print(f"✅ 3. Created portfolio (ID: {portfolio_id}): OK")

    # 4. Download CSV template
    r = client.get(f"{BASE_URL}/portfolios/csv/template")
    assert r.status_code == 200
    assert "ticker,name,quantity,average_cost" in r.text
    print("✅ 4. Downloaded CSV template: OK")

    # 5. Preview CSV Upload
    csv_bytes = b"""ticker,name,quantity,average_cost,asset_class,sector
RELIANCE.NS,Reliance Industries,10,2500.0,equity,Energy
TCS.NS,Tata Consultancy Services,5,3800.0,equity,Information Technology
"""
    files = {"file": ("holdings.csv", io.BytesIO(csv_bytes), "text/csv")}
    r = client.post(f"{BASE_URL}/portfolios/{portfolio_id}/csv/preview", headers=auth_header, files=files)
    assert r.status_code == 200, f"Preview failed: {r.text}"
    preview_data = r.json()
    assert preview_data["can_commit"] is True
    assert preview_data["valid_rows_count"] == 2
    assert preview_data["errors_count"] == 0
    print(f"✅ 5. CSV preview validated 2 rows (0 errors): OK")

    # 6. Commit CSV Upload Atomically
    files_commit = {"file": ("holdings.csv", io.BytesIO(csv_bytes), "text/csv")}
    r = client.post(f"{BASE_URL}/portfolios/{portfolio_id}/csv/commit", headers=auth_header, files=files_commit)
    assert r.status_code == 201, f"Commit failed: {r.text}"
    assert r.json()["imported_count"] == 2
    print("✅ 6. Atomic CSV commit succeeded (2 holdings inserted): OK")

    # 7. Portfolio Valuation Endpoint
    r = client.get(f"{BASE_URL}/portfolios/{portfolio_id}/valuation", headers=auth_header)
    assert r.status_code == 200, f"Valuation failed: {r.text}"
    val_data = r.json()
    assert val_data["portfolio_id"] == portfolio_id
    assert val_data["reporting_currency"] == "INR"
    assert val_data["holdings_count"] == 2
    # Cost basis: 10*2500 + 5*3800 = 25000 + 19000 = 44000
    assert val_data["total_cost_basis"] == 44000.0
    print(f"✅ 7. Portfolio valuation: Cost Basis = ₹{val_data['total_cost_basis']:,}, Priced Holdings = {val_data['valued_holdings_count']}/{val_data['holdings_count']}: OK")

    # 8. User Isolation: User 2 cannot access valuation or upload to User 1's portfolio
    u2_email = f"p2_u2_{uuid.uuid4().hex[:6]}@foliopulse.io"
    r2 = client.post(f"{BASE_URL}/auth/register", json={
        "email": u2_email,
        "full_name": "Unauthorized User",
        "password": "StrongPassword2"
    })
    u2_header = {"Authorization": f"Bearer {r2.json()['access_token']}"}

    forbidden_val = client.get(f"{BASE_URL}/portfolios/{portfolio_id}/valuation", headers=u2_header)
    assert forbidden_val.status_code == 404
    forbidden_csv = client.post(f"{BASE_URL}/portfolios/{portfolio_id}/csv/preview", headers=u2_header, files={"file": ("h.csv", io.BytesIO(csv_bytes), "text/csv")})
    assert forbidden_csv.status_code == 404
    print("✅ 8. User isolation on valuation & CSV endpoints (404 Not Found): OK")

    print("\n🎉 ALL PHASE 2 LIVE END-TO-END VERIFICATION CHECKS PASSED!")


if __name__ == "__main__":
    run_phase2_verification()
