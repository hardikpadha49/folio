"""
FolioPulse AI — Unit & Integration Tests for CSV Import Engine

Tests:
- Template download endpoint
- Valid CSV parsing and preview calculation
- Row-level validation errors:
  - Missing required columns
  - Negative/zero quantity and cost
  - Invalid asset class
  - Duplicate ticker in same CSV
  - Ticker already existing in portfolio
- Defense against CSV Formula Injection (CWE-1236)
- Atomic commit endpoint (full rollback on error)
- User isolation enforcement
"""
import io
import pytest
from app.services.csv_import import CSVImportService, _sanitize_cell_text


# ─────────────────────────────────────────────────────────────────────────────
# Unit Tests: Sanitization & Parsing
# ─────────────────────────────────────────────────────────────────────────────
def test_csv_formula_injection_defense():
    assert _sanitize_cell_text("=CMD|' /C calc'!A0") == "CMD|' /C calc'!A0"
    assert _sanitize_cell_text("+1+2") == "1+2"
    assert _sanitize_cell_text("@SUM(A1:A10)") == "SUM(A1:A10)"
    assert _sanitize_cell_text("-DANGEROUS") == "DANGEROUS"
    assert _sanitize_cell_text("   =Clean Me   ") == "Clean Me"
    assert _sanitize_cell_text("Normal Text") == "Normal Text"


def test_valid_csv_preview():
    csv_content = b"""ticker,name,quantity,average_cost,asset_class,sector
RELIANCE.NS,Reliance Industries,10,2500.0,equity,Energy
TCS.NS,Tata Consultancy Services,5,3800.0,equity,Tech
"""
    preview = CSVImportService.parse_and_validate(csv_content)
    assert preview.can_commit is True
    assert preview.total_rows == 2
    assert preview.valid_rows_count == 2
    assert preview.errors_count == 0
    assert preview.valid_rows[0].ticker == "RELIANCE.NS"
    assert preview.valid_rows[0].invested_value == 25000.0
    assert preview.valid_rows[1].ticker == "TCS.NS"
    assert preview.valid_rows[1].invested_value == 19000.0


def test_csv_validation_errors():
    # Row 2: negative quantity (-5)
    # Row 3: negative cost (-100)
    # Row 4: invalid asset class (magic)
    # Row 5: duplicate ticker (RELIANCE.NS)
    csv_content = b"""ticker,name,quantity,average_cost,asset_class,sector
RELIANCE.NS,Reliance, -5 , 2500.0 , equity , Energy
TCS.NS,TCS, 10 , -100.0 , equity , Tech
INFY.NS,Infosys, 10 , 1500.0 , magic , Tech
RELIANCE.NS,Reliance Duplicate, 2 , 2500.0 , equity , Energy
"""
    preview = CSVImportService.parse_and_validate(csv_content)
    assert preview.can_commit is False
    assert preview.errors_count == 4
    err_cols = [e.column for e in preview.errors]
    assert "quantity" in err_cols
    assert "average_cost" in err_cols
    assert "asset_class" in err_cols
    assert "ticker" in err_cols


def test_csv_rejects_already_existing_portfolio_ticker():
    csv_content = b"""ticker,quantity,average_cost
RELIANCE.NS,10,2500
NEW.NS,5,100
"""
    preview = CSVImportService.parse_and_validate(
        csv_content, existing_tickers={"RELIANCE.NS"}
    )
    assert preview.can_commit is False
    assert preview.errors_count == 1
    assert "already exists" in preview.errors[0].message


# ─────────────────────────────────────────────────────────────────────────────
# API Endpoint Integration Tests
# ─────────────────────────────────────────────────────────────────────────────
USER_CSV = {"email": "csv_user@test.com", "full_name": "CSV User", "password": "SecurePass1"}
OTHER_CSV = {"email": "other_csv@test.com", "full_name": "Other CSV", "password": "SecurePass2"}


def test_download_csv_template(client):
    resp = client.get("/api/v1/portfolios/csv/template")
    assert resp.status_code == 200
    assert "text/csv" in resp.headers["content-type"]
    assert "ticker,name,quantity,average_cost" in resp.text


def test_csv_preview_api_endpoint(client):
    r = client.post("/api/v1/auth/register", json=USER_CSV)
    token = r.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    p = client.post("/api/v1/portfolios", json={"name": "CSV Portfolio"}, headers=headers).json()
    p_id = p["id"]

    csv_data = b"ticker,quantity,average_cost\nAAPL,5,150.0\n"
    files = {"file": ("test.csv", io.BytesIO(csv_data), "text/csv")}

    resp = client.post(f"/api/v1/portfolios/{p_id}/csv/preview", headers=headers, files=files)
    assert resp.status_code == 200
    data = resp.json()
    assert data["can_commit"] is True
    assert data["valid_rows_count"] == 1
    assert data["valid_rows"][0]["ticker"] == "AAPL"


def test_csv_atomic_commit_and_rollback_on_conflict(client):
    r1 = client.post("/api/v1/auth/register", json=USER_CSV)
    token1 = r1.json()["access_token"]
    headers1 = {"Authorization": f"Bearer {token1}"}

    p = client.post("/api/v1/portfolios", json={"name": "Commit Portfolio"}, headers=headers1).json()
    p_id = p["id"]

    # 1. Commit valid CSV
    csv_data = b"ticker,name,quantity,average_cost,asset_class,sector\nINFY.NS,Infosys,10,1600.0,equity,IT\nWIPRO.NS,Wipro,20,450.0,equity,IT\n"
    files = {"file": ("holdings.csv", io.BytesIO(csv_data), "text/csv")}

    commit_resp = client.post(f"/api/v1/portfolios/{p_id}/csv/commit", headers=headers1, files=files)
    assert commit_resp.status_code == 201
    assert commit_resp.json()["imported_count"] == 2

    # Verify holdings are now in database
    list_resp = client.get(f"/api/v1/portfolios/{p_id}/holdings", headers=headers1)
    assert list_resp.status_code == 200
    assert len(list_resp.json()) == 2

    # 2. Re-uploading the same CSV must fail cleanly (rejects duplicates, does not add any extra holdings)
    files_again = {"file": ("holdings.csv", io.BytesIO(csv_data), "text/csv")}
    recommit_resp = client.post(f"/api/v1/portfolios/{p_id}/csv/commit", headers=headers1, files=files_again)
    assert recommit_resp.status_code == 422

    # Verify no partial inserts occurred
    list_after = client.get(f"/api/v1/portfolios/{p_id}/holdings", headers=headers1)
    assert len(list_after.json()) == 2


def test_csv_user_isolation(client):
    r1 = client.post("/api/v1/auth/register", json=USER_CSV)
    token1 = r1.json()["access_token"]
    headers1 = {"Authorization": f"Bearer {token1}"}

    r2 = client.post("/api/v1/auth/register", json=OTHER_CSV)
    token2 = r2.json()["access_token"]
    headers2 = {"Authorization": f"Bearer {token2}"}

    p = client.post("/api/v1/portfolios", json={"name": "User 1 P"}, headers=headers1).json()
    p_id = p["id"]

    csv_data = b"ticker,quantity,average_cost\nAAPL,5,150.0\n"
    files = {"file": ("test.csv", io.BytesIO(csv_data), "text/csv")}

    # User 2 tries to preview or commit to User 1's portfolio -> 404
    resp_prev = client.post(f"/api/v1/portfolios/{p_id}/csv/preview", headers=headers2, files=files)
    assert resp_prev.status_code == 404

    files_commit = {"file": ("test.csv", io.BytesIO(csv_data), "text/csv")}
    resp_comm = client.post(f"/api/v1/portfolios/{p_id}/csv/commit", headers=headers2, files=files_commit)
    assert resp_comm.status_code == 404
