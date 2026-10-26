"""
FolioPulse AI — Unit & Integration Tests for Portfolio Valuation Engine

Tests:
- Valuation calculation: cost basis, market value, unrealized P&L, allocation %
- Preservation of original cost basis (never overwritten by current market price)
- Multi-currency valuation (USD holding in INR portfolio)
- Graceful handling of unpriced holdings (partial valuation)
- Authenticated valuation endpoint with user isolation
"""
import uuid
import pytest
from unittest.mock import AsyncMock

from app.models.user import Portfolio, Holding
from app.services.market_data.base import QuoteData
from app.services.valuation import PortfolioValuationService


@pytest.fixture
def sample_portfolio():
    p = Portfolio(
        id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        name="Tech & Blue Chip",
        currency="INR",
        is_active=True,
    )
    h1 = Holding(
        id=uuid.uuid4(),
        portfolio_id=p.id,
        ticker="RELIANCE.NS",
        name="Reliance",
        quantity=10.0,
        average_cost=2500.0,  # cost_basis = 25000.0
        asset_class="equity",
    )
    h2 = Holding(
        id=uuid.uuid4(),
        portfolio_id=p.id,
        ticker="TCS.NS",
        name="TCS",
        quantity=5.0,
        average_cost=3000.0,  # cost_basis = 15000.0
        asset_class="equity",
    )
    p.holdings = [h1, h2]
    return p


@pytest.mark.asyncio
async def test_valuation_calculation_and_cost_basis_preservation(sample_portfolio):
    mock_market_data = AsyncMock()
    # Live prices differ from purchase cost
    mock_market_data.get_quotes_batch.return_value = {
        "RELIANCE.NS": QuoteData(
            symbol="RELIANCE.NS",
            price=3000.0,  # Up from 2500
            currency="INR",
            previous_close=2950.0,
            change=50.0,
            change_percent=1.69,
            provider="mock",
        ),
        "TCS.NS": QuoteData(
            symbol="TCS.NS",
            price=2800.0,  # Down from 3000
            currency="INR",
            previous_close=2850.0,
            change=-50.0,
            change_percent=-1.75,
            provider="mock",
        ),
    }

    service = PortfolioValuationService(market_data_service=mock_market_data)
    valuation = await service.value_portfolio(sample_portfolio)

    assert valuation.portfolio_id == sample_portfolio.id
    assert valuation.reporting_currency == "INR"
    assert valuation.valuation_complete is True
    assert valuation.holdings_count == 2
    assert valuation.valued_holdings_count == 2

    # Cost basis MUST be preserved: 10*2500 + 5*3000 = 25000 + 15000 = 40000
    assert valuation.total_cost_basis == 40000.0

    # Market value: 10*3000 + 5*2800 = 30000 + 14000 = 44000.0
    assert valuation.total_market_value == 44000.0

    # Total Unrealized P&L: 44000 - 40000 = +4000.0 (+10.0%)
    assert valuation.total_unrealized_pnl == 4000.0
    assert valuation.total_unrealized_pnl_percent == 10.0

    # Holdings check
    rel = next(h for h in valuation.holdings if h.ticker == "RELIANCE.NS")
    assert rel.cost_basis == 25000.0
    assert rel.market_value == 30000.0
    assert rel.unrealized_pnl == 5000.0
    assert rel.unrealized_pnl_percent == 20.0
    # Allocation: 30000 / 44000 = ~68.18%
    assert rel.allocation_percent == round((30000 / 44000) * 100, 2)

    tcs = next(h for h in valuation.holdings if h.ticker == "TCS.NS")
    assert tcs.cost_basis == 15000.0
    assert tcs.market_value == 14000.0
    assert tcs.unrealized_pnl == -1000.0
    # Allocation: 14000 / 44000 = ~31.82%
    assert tcs.allocation_percent == round((14000 / 44000) * 100, 2)


@pytest.mark.asyncio
async def test_valuation_multi_currency_conversion():
    p = Portfolio(
        id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        name="Global Tech",
        currency="INR",
        is_active=True,
    )
    h = Holding(
        id=uuid.uuid4(),
        portfolio_id=p.id,
        ticker="AAPL",
        quantity=2.0,
        average_cost=15000.0,  # purchased at ₹15,000 each = ₹30,000 cost basis
        asset_class="equity",
    )
    p.holdings = [h]

    mock_market_data = AsyncMock()
    mock_market_data.get_quotes_batch.return_value = {
        "AAPL": QuoteData(
            symbol="AAPL",
            price=200.0,  # USD
            currency="USD",
            previous_close=195.0,
            change=5.0,
            change_percent=2.56,
            provider="mock",
        )
    }
    # Mock FX rate: 1 USD = 85.0 INR
    mock_market_data.get_fx_rate.return_value = 85.0

    service = PortfolioValuationService(market_data_service=mock_market_data)
    valuation = await service.value_portfolio(p)

    # 2 AAPL * $200 = $400 * 85 INR/USD = ₹34,000 market value
    assert valuation.total_market_value == 34000.0
    assert valuation.total_cost_basis == 30000.0
    assert valuation.total_unrealized_pnl == 4000.0


@pytest.mark.asyncio
async def test_valuation_unpriced_holding_graceful_handling():
    p = Portfolio(
        id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        name="Mixed Portfolio",
        currency="INR",
        is_active=True,
    )
    h1 = Holding(
        id=uuid.uuid4(),
        portfolio_id=p.id,
        ticker="VALID.NS",
        quantity=10.0,
        average_cost=100.0,
        asset_class="equity",
    )
    h2 = Holding(
        id=uuid.uuid4(),
        portfolio_id=p.id,
        ticker="DELISTED.NS",
        quantity=5.0,
        average_cost=50.0,
        asset_class="equity",
    )
    p.holdings = [h1, h2]

    mock_market_data = AsyncMock()
    mock_market_data.get_quotes_batch.return_value = {
        "VALID.NS": QuoteData(
            symbol="VALID.NS",
            price=120.0,
            currency="INR",
            previous_close=120.0,
            change=0.0,
            change_percent=0.0,
            provider="mock",
        ),
        "DELISTED.NS": None,  # Provider failed to price
    }

    service = PortfolioValuationService(market_data_service=mock_market_data)
    valuation = await service.value_portfolio(p)

    assert valuation.valuation_complete is False
    assert valuation.holdings_count == 2
    assert valuation.valued_holdings_count == 1
    unpriced = next(h for h in valuation.holdings if h.ticker == "DELISTED.NS")
    assert unpriced.data_status == "UNPRICED"
    assert unpriced.market_price is None


# ─────────────────────────────────────────────────────────────────────────────
# Integration Endpoint Test
# ─────────────────────────────────────────────────────────────────────────────
USER_VAL = {"email": "val_user@test.com", "full_name": "Valuation User", "password": "SecurePass1"}
OTHER_USER = {"email": "other_val@test.com", "full_name": "Other User", "password": "SecurePass2"}


def test_valuation_api_user_isolation(client):
    r1 = client.post("/api/v1/auth/register", json=USER_VAL)
    t1 = r1.json()["access_token"]
    h1 = {"Authorization": f"Bearer {t1}"}

    r2 = client.post("/api/v1/auth/register", json=OTHER_USER)
    t2 = r2.json()["access_token"]
    h2 = {"Authorization": f"Bearer {t2}"}

    # User 1 creates portfolio
    p_resp = client.post("/api/v1/portfolios", json={"name": "P_Val"}, headers=h1)
    p_id = p_resp.json()["id"]

    # User 1 values it
    v_resp = client.get(f"/api/v1/portfolios/{p_id}/valuation", headers=h1)
    assert v_resp.status_code == 200
    assert v_resp.json()["portfolio_id"] == p_id

    # User 2 tries to value User 1's portfolio -> 404
    forbidden_resp = client.get(f"/api/v1/portfolios/{p_id}/valuation", headers=h2)
    assert forbidden_resp.status_code == 404
