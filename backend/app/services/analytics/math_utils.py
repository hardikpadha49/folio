"""
FolioPulse AI — Financial Analytics Mathematical Utilities

Reusable, pure mathematical functions for:
- Daily, cumulative, and annualized returns
- Time-Weighted Rate of Return (TWR)
- Money-Weighted Rate of Return (MWR / XIRR) via robust root-finding
- Drawdown series and Maximum Drawdown
- Downside semi-deviation and annualization
- Herfindahl-Hirschman Index (HHI) and Shannon Entropy

All formulas are mathematically rigorous, handle numerical edge cases,
and never produce NaN or infinite values without documented fallback.
"""
import math
from datetime import date, datetime
from typing import List, Optional, Sequence, Tuple
import numpy as np
from scipy import optimize


TRADING_DAYS_PER_YEAR = 252


def calculate_daily_returns(prices: Sequence[float]) -> np.ndarray:
    """
    Calculate simple percentage daily returns: R_t = (P_t - P_{t-1}) / P_{t-1}.
    Returns empty array if fewer than 2 prices are provided.
    """
    arr = np.asarray(prices, dtype=float)
    if len(arr) < 2:
        return np.array([], dtype=float)
    # Check for non-positive previous prices
    prev = arr[:-1]
    curr = arr[1:]
    with np.errstate(divide="ignore", invalid="ignore"):
        returns = np.where(prev > 0, (curr - prev) / prev, 0.0)
    # Replace any potential inf or NaN with 0.0
    returns = np.nan_to_num(returns, nan=0.0, posinf=0.0, neginf=0.0)
    return returns


def calculate_cumulative_returns(daily_returns: Sequence[float]) -> np.ndarray:
    """
    Calculate cumulative wealth index returns: (1 + R_cum) = prod(1 + R_t).
    Returns array of cumulative returns starting from the first period.
    """
    if len(daily_returns) == 0:
        return np.array([], dtype=float)
    arr = np.asarray(daily_returns, dtype=float)
    wealth_index = np.cumprod(1.0 + arr)
    return wealth_index - 1.0


def calculate_total_return(start_value: float, end_value: float) -> float:
    """
    Total holding period return: (end - start) / start.
    Returns 0.0 if start_value <= 0.
    """
    if start_value <= 0:
        return 0.0
    return round((end_value - start_value) / start_value, 6)


def calculate_annualized_return(
    total_return: float, num_periods: int, periods_per_year: int = TRADING_DAYS_PER_YEAR
) -> Optional[float]:
    """
    Compound Annual Growth Rate (CAGR): (1 + R_total)**(periods_per_year / num_periods) - 1.
    Requires at least 20 periods to avoid extreme statistical distortion on short periods.
    """
    if num_periods < 20 or (1.0 + total_return) <= 0:
        return None
    try:
        cagr = (1.0 + total_return) ** (periods_per_year / num_periods) - 1.0
        if math.isnan(cagr) or math.isinf(cagr):
            return None
        return round(float(cagr), 6)
    except (ValueError, OverflowError):
        return None


def calculate_annualized_volatility(
    daily_returns: Sequence[float], periods_per_year: int = TRADING_DAYS_PER_YEAR
) -> float:
    """
    Sample standard deviation of daily returns annualized by sqrt(252).
    Uses ddof=1 (unbiased sample standard deviation).
    """
    if len(daily_returns) < 2:
        return 0.0
    arr = np.asarray(daily_returns, dtype=float)
    std = float(np.std(arr, ddof=1))
    if math.isnan(std) or math.isinf(std) or std <= 0.0:
        return 0.0
    return round(std * math.sqrt(periods_per_year), 6)


def calculate_downside_deviation(
    daily_returns: Sequence[float],
    mar_daily: float = 0.0,
    periods_per_year: int = TRADING_DAYS_PER_YEAR,
) -> float:
    """
    Annualized downside semi-deviation for returns falling below the Minimum Acceptable Return (MAR).
    Used in Sortino ratio calculation.
    """
    if len(daily_returns) < 2:
        return 0.0
    arr = np.asarray(daily_returns, dtype=float)
    downside_diff = np.minimum(0.0, arr - mar_daily)
    downside_var = float(np.mean(downside_diff**2))
    downside_std = math.sqrt(downside_var)
    return round(downside_std * math.sqrt(periods_per_year), 6)


def calculate_sharpe_ratio(
    annualized_return: Optional[float],
    annualized_volatility: float,
    risk_free_rate: float = 0.068,  # Default 6.8% (e.g. Indian 10Y G-Sec)
) -> Optional[float]:
    """
    Sharpe Ratio = (R_annualized - R_f) / Volatility_annualized.
    Returns None if volatility is zero or returns cannot be annualized.
    """
    if annualized_return is None or annualized_volatility <= 1e-6:
        return None
    sharpe = (annualized_return - risk_free_rate) / annualized_volatility
    if math.isnan(sharpe) or math.isinf(sharpe):
        return None
    return round(float(sharpe), 4)


def calculate_sortino_ratio(
    annualized_return: Optional[float],
    downside_deviation: float,
    risk_free_rate: float = 0.068,
) -> Optional[float]:
    """
    Sortino Ratio = (R_annualized - R_f) / Downside_Deviation_annualized.
    Penalizes only downside volatility.
    """
    if annualized_return is None or downside_deviation <= 1e-6:
        return None
    sortino = (annualized_return - risk_free_rate) / downside_deviation
    if math.isnan(sortino) or math.isinf(sortino):
        return None
    return round(float(sortino), 4)


def calculate_drawdown_series(prices_or_wealth: Sequence[float]) -> Tuple[np.ndarray, float]:
    """
    Calculate the underwater drawdown series and maximum drawdown.
    DD_t = (P_t - HighWaterMark_t) / HighWaterMark_t.
    Returns (drawdown_array, max_drawdown_as_positive_float).
    """
    if len(prices_or_wealth) < 1:
        return np.array([], dtype=float), 0.0
    arr = np.asarray(prices_or_wealth, dtype=float)
    peaks = np.maximum.accumulate(arr)
    with np.errstate(divide="ignore", invalid="ignore"):
        drawdowns = np.where(peaks > 0, (arr - peaks) / peaks, 0.0)
    drawdowns = np.nan_to_num(drawdowns, nan=0.0)
    min_dd = float(np.min(drawdowns))  # e.g. -0.25 (-25%)
    max_dd = abs(min_dd) if min_dd < 0 else 0.0
    return drawdowns, round(max_dd, 6)


def calculate_historical_var(
    daily_returns: Sequence[float], confidence_level: float = 0.95
) -> Optional[float]:
    """
    Historical Value at Risk (VaR).
    Defined as the positive percentage loss:
    e.g. at 95% confidence, VaR = -percentile(returns, 5%, method="lower").
    If VaR = 0.0215, it means with 95% confidence, the daily loss will not exceed 2.15%.
    """
    if len(daily_returns) < 10:
        return None
    arr = np.asarray(daily_returns, dtype=float)
    alpha = (1.0 - confidence_level) * 100.0
    cutoff = float(np.percentile(arr, alpha, method="lower"))
    # Return as positive loss magnitude
    var = -cutoff if cutoff < 0 else 0.0
    return round(var, 6)


def calculate_historical_cvar(
    daily_returns: Sequence[float], confidence_level: float = 0.95
) -> Optional[float]:
    """
    Historical Conditional Value at Risk (CVaR / Expected Shortfall).
    Expected percentage loss given that the loss exceeds or meets the VaR threshold.
    Returns positive percentage value.
    """
    if len(daily_returns) < 10:
        return None
    arr = np.asarray(daily_returns, dtype=float)
    alpha = (1.0 - confidence_level) * 100.0
    cutoff = float(np.percentile(arr, alpha, method="lower"))
    tail_losses = arr[arr <= cutoff]
    if len(tail_losses) == 0:
        return calculate_historical_var(daily_returns, confidence_level)
    expected_tail = float(np.mean(tail_losses))
    cvar = -expected_tail if expected_tail < 0 else 0.0
    return round(cvar, 6)


def calculate_hhi(weights: Sequence[float]) -> float:
    """
    Herfindahl-Hirschman Index (HHI): sum of squared portfolio weights.
    Weights must sum to 1.0 (or normalized). Range: [1/N, 1.0].
    """
    if len(weights) == 0:
        return 1.0
    arr = np.asarray(weights, dtype=float)
    total = np.sum(arr)
    if total <= 0:
        return 1.0
    norm_w = arr / total
    return round(float(np.sum(norm_w**2)), 6)


def calculate_effective_n(weights: Sequence[float]) -> float:
    """
    Effective number of holdings: inverse of HHI = 1 / sum(w_i^2).
    Range: [1.0, N].
    """
    hhi = calculate_hhi(weights)
    if hhi <= 1e-6:
        return float(len(weights))
    return round(1.0 / hhi, 2)


def calculate_shannon_entropy(weights: Sequence[float]) -> float:
    """
    Shannon Entropy: -sum(w_i * ln(w_i)).
    Measures dispersion across categories (asset classes, sectors).
    """
    arr = np.asarray(weights, dtype=float)
    arr = arr[arr > 0]
    total = np.sum(arr)
    if total <= 0 or len(arr) <= 1:
        return 0.0
    p = arr / total
    entropy = -np.sum(p * np.log(p))
    return float(entropy)


def calculate_xirr(
    cash_flows: Sequence[float],
    dates: Sequence[date],
    guess: float = 0.1,
) -> Optional[float]:
    """
    Calculate Money-Weighted Rate of Return / Extended Internal Rate of Return (XIRR).
    Solves sum(C_i / (1 + r)**((d_i - d_0) / 365)) = 0.

    Requirements:
    - At least one negative cash flow (investment/outflow) and one positive (terminal value/inflow).
    - Uses robust bounded root finding with bisection fallback.
    - Returns annualized decimal return (e.g. 0.15 = 15% p.a.), or None if non-convergent.
    """
    if len(cash_flows) != len(dates) or len(cash_flows) < 2:
        return None

    # Check for presence of both signs
    has_pos = any(cf > 0 for cf in cash_flows)
    has_neg = any(cf < 0 for cf in cash_flows)
    if not (has_pos and has_neg):
        return None

    d0 = dates[0]
    day_fractions = np.array([(d - d0).days / 365.0 for d in dates], dtype=float)
    cfs = np.array(cash_flows, dtype=float)

    def npv(r: float) -> float:
        if r <= -0.999999:
            return float("inf")
        with np.errstate(over="ignore", invalid="ignore"):
            val = np.sum(cfs / ((1.0 + r) ** day_fractions))
        return float(val)

    # Attempt Brentq within reasonable bounds [-0.99, 10.0]
    try:
        # Check signs at boundaries to ensure root exists between them
        f_low = npv(-0.95)
        f_high = npv(10.0)
        if f_low * f_high < 0:
            sol = optimize.brentq(npv, -0.95, 10.0, maxiter=200)
            return round(float(sol), 6)
    except Exception:
        pass

    # Fallback to Newton-Raphson with bounds
    try:
        sol = optimize.newton(npv, guess, maxiter=100)
        if not math.isnan(sol) and not math.isinf(sol) and -0.99 < sol < 50.0:
            return round(float(sol), 6)
    except Exception:
        pass

    return None
