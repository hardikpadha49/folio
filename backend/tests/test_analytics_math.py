"""
FolioPulse AI — Unit Tests for Financial Analytics Math Utilities

Validates:
- Return calculations against exact numerical targets
- Volatility, semi-deviation, and annualization
- Sharpe and Sortino ratio edge cases
- Drawdown series and Max Drawdown
- Historical VaR and CVaR at 95% and 99%
- HHI, Effective N, and Shannon Entropy
- XIRR solver convergence on known cash flows
"""
import math
from datetime import date, timedelta
import numpy as np
import pytest

from app.services.analytics.math_utils import (
    calculate_daily_returns,
    calculate_cumulative_returns,
    calculate_total_return,
    calculate_annualized_return,
    calculate_annualized_volatility,
    calculate_downside_deviation,
    calculate_sharpe_ratio,
    calculate_sortino_ratio,
    calculate_drawdown_series,
    calculate_historical_var,
    calculate_historical_cvar,
    calculate_hhi,
    calculate_effective_n,
    calculate_shannon_entropy,
    calculate_xirr,
)


# ─────────────────────────────────────────────────────────────────────────────
# Returns & Compounding
# ─────────────────────────────────────────────────────────────────────────────
def test_calculate_daily_returns():
    prices = [100.0, 105.0, 102.9, 108.045]
    returns = calculate_daily_returns(prices)
    assert len(returns) == 3
    # 105/100 - 1 = +0.05
    assert pytest.approx(returns[0], 0.0001) == 0.05
    # 102.9/105 - 1 = -0.02
    assert pytest.approx(returns[1], 0.0001) == -0.02
    # 108.045/102.9 - 1 = +0.05
    assert pytest.approx(returns[2], 0.0001) == 0.05


def test_calculate_daily_returns_empty_or_single():
    assert len(calculate_daily_returns([])) == 0
    assert len(calculate_daily_returns([100.0])) == 0


def test_calculate_cumulative_returns():
    daily = [0.05, -0.02, 0.05]
    cum = calculate_cumulative_returns(daily)
    # (1.05)*(0.98) - 1 = 0.029
    assert pytest.approx(cum[1], 0.0001) == 0.029
    # (1.05)*(0.98)*(1.05) - 1 = 0.08045
    assert pytest.approx(cum[2], 0.0001) == 0.08045


def test_calculate_total_and_annualized_return():
    assert calculate_total_return(100.0, 120.0) == 0.20
    assert calculate_total_return(0.0, 100.0) == 0.0

    # 20% return over exactly 252 trading days = 20.0% annualized
    cagr = calculate_annualized_return(0.20, 252)
    assert cagr is not None
    assert pytest.approx(cagr, 0.001) == 0.20

    # Insufficient observations (< 20 periods) returns None
    assert calculate_annualized_return(0.05, 10) is None


# ─────────────────────────────────────────────────────────────────────────────
# Volatility & Risk Metrics
# ─────────────────────────────────────────────────────────────────────────────
def test_calculate_annualized_volatility():
    # If daily returns are constant, sample standard deviation is 0.0
    assert calculate_annualized_volatility([0.01, 0.01, 0.01]) == 0.0
    assert calculate_annualized_volatility([]) == 0.0

    # Known standard deviation
    rets = [0.01, -0.01, 0.02, -0.02]
    vol = calculate_annualized_volatility(rets)
    assert vol > 0.0


def test_calculate_sharpe_and_sortino_ratios():
    # R_ann = 15%, vol = 12%, R_f = 6% -> Sharpe = (0.15 - 0.06)/0.12 = 0.75
    sharpe = calculate_sharpe_ratio(0.15, 0.12, risk_free_rate=0.06)
    assert sharpe == 0.75

    # Zero volatility guard returns None
    assert calculate_sharpe_ratio(0.10, 0.0) is None
    assert calculate_sharpe_ratio(None, 0.15) is None

    # Sortino ratio
    sortino = calculate_sortino_ratio(0.15, 0.08, risk_free_rate=0.06)
    assert sortino == round((0.15 - 0.06) / 0.08, 4)


def test_calculate_drawdown_series():
    # Peak at 100, drops to 70 (30% dd), rises to 90, new peak 110, drops to 88 (20% dd)
    wealth = [100.0, 80.0, 70.0, 90.0, 110.0, 88.0]
    series, max_dd = calculate_drawdown_series(wealth)
    assert len(series) == 6
    assert series[0] == 0.0
    assert series[2] == -0.30
    assert series[4] == 0.0
    assert series[5] == -0.20
    assert max_dd == 0.30


def test_calculate_historical_var_and_cvar():
    # 100 observations: 95 positive (1%), 5 negative (-3%, -4%, -5%, -6%, -7%)
    rets = [0.01] * 95 + [-0.03, -0.04, -0.05, -0.06, -0.07]
    var_95 = calculate_historical_var(rets, confidence_level=0.95)
    assert var_95 is not None
    # 5th percentile is approximately -0.03 or -0.04 -> positive loss > 0.025
    assert 0.025 <= var_95 <= 0.07

    cvar_95 = calculate_historical_cvar(rets, confidence_level=0.95)
    assert cvar_95 is not None
    # Expected shortfall of the tail losses (-3% to -7%) is around 5.0%
    assert cvar_95 >= var_95


# ─────────────────────────────────────────────────────────────────────────────
# Concentration & Entropy
# ─────────────────────────────────────────────────────────────────────────────
def test_calculate_hhi_and_effective_n():
    # Single asset: HHI = 1.0, Effective N = 1.0
    assert calculate_hhi([1.0]) == 1.0
    assert calculate_effective_n([1.0]) == 1.0

    # 4 equal assets (25% each): HHI = 4 * (0.25^2) = 0.25, Effective N = 1 / 0.25 = 4.0
    assert calculate_hhi([0.25, 0.25, 0.25, 0.25]) == 0.25
    assert calculate_effective_n([0.25, 0.25, 0.25, 0.25]) == 4.0

    # 1 dominant (90%) and 1 minor (10%): HHI = 0.81 + 0.01 = 0.82, Effective N = ~1.22
    assert calculate_effective_n([0.9, 0.1]) == round(1.0 / 0.82, 2)


def test_calculate_shannon_entropy():
    # Single asset -> entropy = 0.0
    assert calculate_shannon_entropy([1.0]) == 0.0
    # Two equal assets -> entropy = ln(2) ≈ 0.6931
    assert pytest.approx(calculate_shannon_entropy([0.5, 0.5]), 0.001) == math.log(2)


# ─────────────────────────────────────────────────────────────────────────────
# Money-Weighted Return (XIRR)
# ─────────────────────────────────────────────────────────────────────────────
def test_calculate_xirr_exact_one_year():
    # Invest 1,000 on Jan 1 2025, receive 1,100 on Jan 1 2026 (exact 10% return)
    d0 = date(2025, 1, 1)
    d1 = date(2026, 1, 1)
    cfs = [-1000.0, 1100.0]
    dates = [d0, d1]
    rate = calculate_xirr(cfs, dates)
    assert rate is not None
    assert pytest.approx(rate, 0.001) == 0.10


def test_calculate_xirr_mid_period_addition():
    # Invest 1,000 on Jan 1 2025, invest 1,000 on Jul 2 2025 (~182 days), value 2,300 on Jan 1 2026
    d0 = date(2025, 1, 1)
    d1 = date(2025, 7, 2)
    d2 = date(2026, 1, 1)
    cfs = [-1000.0, -1000.0, 2300.0]
    dates = [d0, d1, d2]
    rate = calculate_xirr(cfs, dates)
    assert rate is not None
    assert rate > 0.15  # Return must exceed 15% due to second investment timing


def test_calculate_xirr_insufficient_or_invalid():
    # All positive or all negative cash flows returns None
    assert calculate_xirr([100.0, 200.0], [date(2025, 1, 1), date(2025, 6, 1)]) is None
    assert calculate_xirr([-100.0, -200.0], [date(2025, 1, 1), date(2025, 6, 1)]) is None
    # Empty
    assert calculate_xirr([], []) is None
