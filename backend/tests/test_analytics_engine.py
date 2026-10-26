"""
FolioPulse AI — Analytics Engine Unit & Integration Tests

Tests all 6 analytics engines using deterministic synthetic price histories:
1. PerformanceEngine (returns, CAGR, TWR, MWR, contributions)
2. RiskEngine (volatility, Sharpe, Sortino, VaR/CVaR, HHI, correlation, risk contributions)
3. DiversificationEngine (5-pillar score, rating, explanation)
4. HealthScoreEngine (4-pillar score, status, handling insufficient data)
5. BenchmarkEngine (Beta, Alpha, Tracking Error, Information Ratio)
6. XRayEngine (Asset Class, Sector, Currency exposure)
"""
import pytest
import uuid
from datetime import datetime, timezone, timedelta
from typing import Dict, List
import numpy as np

from app.models.user import Portfolio, Holding
from app.services.market_data.base import HistoricalData, HistoricalBar
from app.services.analytics.performance import PerformanceEngine
from app.services.analytics.risk import RiskEngine
from app.services.analytics.diversification import DiversificationEngine
from app.services.analytics.health import HealthScoreEngine
from app.services.analytics.benchmark import BenchmarkEngine
from app.services.analytics.xray import XRayEngine
from app.schemas.valuation import PortfolioValuationResponse, HoldingValuation


PORT_ID = uuid.uuid4()
USER_ID = uuid.uuid4()
H1_ID = uuid.uuid4()
H2_ID = uuid.uuid4()


def generate_synthetic_history(
    symbol: str,
    currency: str,
    start_price: float,
    daily_returns: List[float],
    start_date: str = "2026-01-01",
) -> HistoricalData:
    """Generate deterministic HistoricalData given a series of daily returns."""
    current_date = datetime.strptime(start_date, "%Y-%m-%d").date()
    current_price = start_price
    bars: List[HistoricalBar] = []

    # First bar
    bars.append(
        HistoricalBar(
            date=current_date.strftime("%Y-%m-%d"),
            open=current_price,
            high=current_price * 1.01,
            low=current_price * 0.99,
            close=current_price,
            volume=100000,
            adj_close=current_price,
        )
    )

    for r in daily_returns:
        current_date += timedelta(days=1)
        # Skip weekends for trading realism
        while current_date.weekday() >= 5:
            current_date += timedelta(days=1)
        current_price = current_price * (1.0 + r)
        bars.append(
            HistoricalBar(
                date=current_date.strftime("%Y-%m-%d"),
                open=round(current_price * 0.998, 2),
                high=round(current_price * 1.015, 2),
                low=round(current_price * 0.985, 2),
                close=round(current_price, 2),
                volume=150000,
                adj_close=round(current_price, 2),
            )
        )

    return HistoricalData(
        symbol=symbol,
        currency=currency,
        provider="TEST_DETERMINISTIC",
        bars=bars,
        retrieved_at=datetime.now(timezone.utc),
    )


@pytest.fixture
def sample_portfolio() -> Portfolio:
    port = Portfolio(
        id=PORT_ID,
        user_id=USER_ID,
        name="Growth Tech & Banking",
        currency="INR",
        created_at=datetime(2025, 1, 1, tzinfo=timezone.utc),
    )
    h1 = Holding(
        id=H1_ID,
        portfolio_id=PORT_ID,
        ticker="TCS.NS",
        asset_class="EQUITY",
        sector="Technology",
        quantity=10.0,
        average_cost=3500.0,  # Cost = 35,000 INR
    )
    h2 = Holding(
        id=H2_ID,
        portfolio_id=PORT_ID,
        ticker="HDFCBANK.NS",
        asset_class="EQUITY",
        sector="Financial Services",
        quantity=20.0,
        average_cost=1500.0,  # Cost = 30,000 INR
    )
    port.holdings = [h1, h2]
    return port


@pytest.fixture
def synthetic_market_history() -> Dict[str, HistoricalData]:
    # 50 days of returns
    np.random.seed(42)
    # Asset 1: steady upward drift (avg 0.15% daily, vol ~1.2%)
    r1 = list(np.random.normal(0.0015, 0.012, 50))
    # Asset 2: moderate return (avg 0.08% daily, vol ~1.5%)
    r2 = list(np.random.normal(0.0008, 0.015, 50))
    # Benchmark: NIFTY 50 (avg 0.09% daily, vol ~1.0%)
    rb = list(np.random.normal(0.0009, 0.010, 50))

    return {
        "TCS.NS": generate_synthetic_history("TCS.NS", "INR", 3500.0, r1),
        "HDFCBANK.NS": generate_synthetic_history("HDFCBANK.NS", "INR", 1500.0, r2),
        "^NSEI": generate_synthetic_history("^NSEI", "INR", 22000.0, rb),
    }


# ==============================================================================
# 1. PerformanceEngine Tests
# ==============================================================================
@pytest.mark.asyncio
async def test_performance_engine_calculation(sample_portfolio, synthetic_market_history):
    engine = PerformanceEngine()
    result = await engine.calculate_performance(
        sample_portfolio, period="1y", custom_history=synthetic_market_history
    )

    assert result.status == "VALID"
    assert result.portfolio_id == PORT_ID
    assert result.reporting_currency == "INR"
    assert result.observation_count == 51  # 1 initial + 50 bars
    assert len(result.history) == 51
    assert result.total_return is not None
    assert result.twr is not None
    assert len(result.contributions) == 2

    # Contribution tickers
    tickers = {c.ticker for c in result.contributions}
    assert tickers == {"TCS.NS", "HDFCBANK.NS"}

    # Weights sum to approximately 1.0 (cost weights: 35000/65000 ~ 0.5385, 30000/65000 ~ 0.4615)
    total_w = sum(c.weight for c in result.contributions)
    assert abs(total_w - 1.0) < 1e-3


@pytest.mark.asyncio
async def test_performance_engine_empty_portfolio():
    port = Portfolio(
        id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        name="Empty",
        currency="USD",
    )
    port.holdings = []
    engine = PerformanceEngine()
    result = await engine.calculate_performance(port)
    assert result.status == "EMPTY"
    assert result.observation_count == 0
    assert result.total_return == 0.0


# ==============================================================================
# 2. RiskEngine Tests
# ==============================================================================
@pytest.mark.asyncio
async def test_risk_engine_calculation(sample_portfolio, synthetic_market_history):
    engine = RiskEngine()
    result = await engine.calculate_risk(
        sample_portfolio,
        period="1y",
        risk_free_rate=0.068,
        custom_history=synthetic_market_history,
    )

    assert result.portfolio_id == PORT_ID
    assert result.observation_count == 50
    assert result.annualized_volatility > 0.0
    assert result.max_drawdown >= 0.0
    assert result.historical_var_95 is not None
    assert result.historical_cvar_95 is not None
    assert result.historical_var_99 is not None
    assert result.historical_cvar_99 is not None

    # HHI and Effective N
    assert 0.0 < result.hhi <= 1.0
    assert 1.0 <= result.effective_n <= 2.0

    # Correlation Matrix
    assert "TCS.NS" in result.correlation_matrix
    assert "HDFCBANK.NS" in result.correlation_matrix
    # Self-correlation is 1.0
    assert result.correlation_matrix["TCS.NS"]["TCS.NS"] == 1.0

    # Risk contributions
    assert len(result.risk_contributions) == 2


# ==============================================================================
# 3. DiversificationEngine Tests
# ==============================================================================
@pytest.mark.asyncio
async def test_diversification_engine(sample_portfolio, synthetic_market_history):
    engine = DiversificationEngine()
    result = await engine.calculate_diversification(
        sample_portfolio, custom_history=synthetic_market_history
    )

    assert result.portfolio_id == PORT_ID
    assert 0.0 <= result.score <= 100.0
    assert result.rating in [
        "Highly Concentrated",
        "Moderate Diversification",
        "Well Diversified",
        "Optimally Diversified",
    ]
    assert len(result.components) == 5
    # Dimensions check
    dim_names = {c.dimension for c in result.components}
    expected_dims = {
        "Holding Breadth",
        "Holding Balance (HHI)",
        "Asset Class Entropy",
        "Sector Entropy",
        "Diversification Ratio",
    }
    assert dim_names == expected_dims


# ==============================================================================
# 4. HealthScoreEngine Tests
# ==============================================================================
@pytest.mark.asyncio
async def test_health_score_engine(sample_portfolio, synthetic_market_history):
    engine = HealthScoreEngine()
    result = await engine.calculate_health(
        sample_portfolio, period="1y", custom_history=synthetic_market_history
    )

    assert result.portfolio_id == PORT_ID
    assert result.status == "HEALTHY"
    assert 0.0 <= result.overall_score <= 100.0
    assert result.rating in ["Critical", "Needs Attention", "Fair", "Strong", "Exceptional"]
    assert len(result.components) == 4
    comp_names = {c.name for c in result.components}
    assert comp_names == {
        "Diversification Health",
        "Concentration Guard",
        "Downside Resilience",
        "Risk-Adjusted Efficiency",
    }
    assert isinstance(result.key_strengths, list)
    assert isinstance(result.key_risks, list)


@pytest.mark.asyncio
async def test_health_score_insufficient_data(sample_portfolio):
    # Only 5 observations -> insufficient data (< 15)
    short_history = {
        "TCS.NS": generate_synthetic_history("TCS.NS", "INR", 3500.0, [0.01, -0.01, 0.005, 0.002]),
        "HDFCBANK.NS": generate_synthetic_history("HDFCBANK.NS", "INR", 1500.0, [0.005, -0.005, 0.002, 0.001]),
    }
    engine = HealthScoreEngine()
    result = await engine.calculate_health(
        sample_portfolio, period="1y", custom_history=short_history
    )
    assert result.status == "INSUFFICIENT_DATA"
    assert "Insufficient historical observations" in result.key_risks[0]


# ==============================================================================
# 5. BenchmarkEngine Tests
# ==============================================================================
@pytest.mark.asyncio
async def test_benchmark_engine_comparison(sample_portfolio, synthetic_market_history):
    engine = BenchmarkEngine()
    result = await engine.compare_benchmark(
        sample_portfolio,
        benchmark_symbol="^NSEI",
        period="1y",
        risk_free_rate=0.068,
        custom_history=synthetic_market_history,
    )

    assert result.portfolio_id == PORT_ID
    assert result.benchmark_symbol == "^NSEI"
    assert result.benchmark_name == "NIFTY 50"
    assert result.observation_count == 50
    assert result.portfolio_return is not None
    assert result.benchmark_return is not None
    assert result.beta is not None
    assert result.alpha is not None
    assert result.tracking_error is not None
    assert len(result.portfolio_series) == 51
    assert len(result.benchmark_series) == 51
    # Check normalized base is 100.0
    assert result.portfolio_series[0].value == 100.0
    assert result.benchmark_series[0].value == 100.0


# ==============================================================================
# 6. XRayEngine Tests
# ==============================================================================
class MockValuationService:
    async def value_portfolio(self, portfolio: Portfolio, force_refresh: bool = False):
        return PortfolioValuationResponse(
            portfolio_id=portfolio.id,
            portfolio_name=portfolio.name,
            reporting_currency=portfolio.currency,
            total_market_value=68000.0,
            total_cost_basis=65000.0,
            total_unrealized_pnl=3000.0,
            total_unrealized_pnl_percent=4.62,
            valuation_complete=True,
            as_of=datetime.now(timezone.utc),
            holdings=[
                HoldingValuation(
                    holding_id=H1_ID,
                    ticker="TCS.NS",
                    asset_class="EQUITY",
                    sector="Technology",
                    quantity=10.0,
                    average_cost=3500.0,
                    cost_basis=35000.0,
                    current_price=3700.0,
                    market_value=37000.0,
                    unrealized_pnl=2000.0,
                    unrealized_pnl_percent=5.71,
                    allocation_percent=54.41,
                    quote_currency="INR",
                    exchange="NSE",
                    price_status="VALID",
                    price_timestamp=datetime.now(timezone.utc),
                    is_stale=False,
                ),
                HoldingValuation(
                    holding_id=H2_ID,
                    ticker="HDFCBANK.NS",
                    asset_class="EQUITY",
                    sector="Financial Services",
                    quantity=20.0,
                    average_cost=1500.0,
                    cost_basis=30000.0,
                    current_price=1550.0,
                    market_value=31000.0,
                    unrealized_pnl=1000.0,
                    unrealized_pnl_percent=3.33,
                    allocation_percent=45.59,
                    quote_currency="INR",
                    exchange="NSE",
                    price_status="VALID",
                    price_timestamp=datetime.now(timezone.utc),
                    is_stale=False,
                ),
            ],
            notes=[],
        )


@pytest.mark.asyncio
async def test_xray_engine_generation(sample_portfolio):
    mock_val = MockValuationService()
    engine = XRayEngine(valuation_service=mock_val)
    xray = await engine.generate_xray(sample_portfolio)

    assert xray.portfolio_id == PORT_ID
    assert xray.reporting_currency == "INR"

    # Asset class breakdown: 100% Equity
    assert len(xray.asset_classes) == 1
    assert xray.asset_classes[0].asset_class.upper() == "EQUITY"
    assert abs(xray.asset_classes[0].market_percentage - 100.0) < 1e-2

    # Sector breakdown: Technology ~54.41%, Financial Services ~45.59%
    assert len(xray.sectors) == 2
    sector_names = {s.sector for s in xray.sectors}
    assert "Technology" in sector_names
    assert "Financial Services" in sector_names

    # Top holdings: 2 holdings, sorted descending
    assert len(xray.top_holdings) == 2
    assert xray.top_holdings[0].ticker == "TCS.NS"
    assert xray.top_holdings[1].ticker == "HDFCBANK.NS"

    # Currency exposure: 100% INR
    assert len(xray.currency_exposure) == 1
    assert xray.currency_exposure[0].currency == "INR"
    assert xray.currency_exposure[0].market_percentage == 100.0
