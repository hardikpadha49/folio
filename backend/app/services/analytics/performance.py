"""
FolioPulse AI — Portfolio Historical Performance Engine

Calculates:
- Asset-level and weighted portfolio daily returns
- Cumulative portfolio returns & normalized value trajectory
- Total return & Annualized Return (CAGR)
- Time-Weighted Return (TWR)
- Money-Weighted Return (MWR / XIRR) with dated transaction cash flows
- Performance contribution per holding
"""
import logging
from datetime import datetime, timezone, date
from typing import Dict, List, Optional
import numpy as np

from app.models.user import Portfolio, Holding
from app.schemas.analytics import (
    PerformanceMetricsResponse,
    PerformanceContribution,
    PerformanceHistoryPoint,
)
from app.services.analytics.math_utils import (
    calculate_daily_returns,
    calculate_cumulative_returns,
    calculate_total_return,
    calculate_annualized_return,
    calculate_xirr,
    TRADING_DAYS_PER_YEAR,
)
from app.services.market_data.service import MarketDataService, get_market_data_service
from app.services.market_data.base import HistoricalData

logger = logging.getLogger(__name__)


class PerformanceEngine:
    """Computes historical portfolio return metrics and time-series."""

    def __init__(self, market_data_service: Optional[MarketDataService] = None):
        self.market_data = market_data_service or get_market_data_service()

    async def calculate_performance(
        self,
        portfolio: Portfolio,
        period: str = "1y",
        custom_history: Optional[Dict[str, HistoricalData]] = None,
    ) -> PerformanceMetricsResponse:
        holdings: List[Holding] = portfolio.holdings or []
        portfolio_name = portfolio.name
        currency = portfolio.currency.upper()

        if not holdings:
            now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            return PerformanceMetricsResponse(
                portfolio_id=portfolio.id,
                portfolio_name=portfolio_name,
                reporting_currency=currency,
                lookback_period=period,
                start_date=now_str,
                end_date=now_str,
                observation_count=0,
                total_return=0.0,
                annualized_return=None,
                twr=0.0,
                mwr_xirr=None,
                mwr_note="No holdings in portfolio.",
                contributions=[],
                history=[],
                status="EMPTY",
                notes=["Portfolio contains no holdings."],
            )

        # 1. Fetch historical series for each holding
        history_map: Dict[str, HistoricalData] = {}
        missing_tickers: List[str] = []

        for h in holdings:
            if custom_history and h.ticker in custom_history:
                history_map[h.ticker] = custom_history[h.ticker]
            else:
                hist = await self.market_data.get_historical(h.ticker, period=period, interval="1d")
                if hist and len(hist.bars) >= 5:
                    history_map[h.ticker] = hist
                else:
                    missing_tickers.append(h.ticker)

        notes = []
        if missing_tickers:
            notes.append(
                f"Historical data unavailable for {len(missing_tickers)} holding(s): {', '.join(missing_tickers)}. Evaluated on remaining assets."
            )

        if not history_map:
            now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            return PerformanceMetricsResponse(
                portfolio_id=portfolio.id,
                portfolio_name=portfolio_name,
                reporting_currency=currency,
                lookback_period=period,
                start_date=now_str,
                end_date=now_str,
                observation_count=0,
                total_return=0.0,
                annualized_return=None,
                twr=0.0,
                mwr_xirr=None,
                mwr_note="Market history unavailable from providers.",
                contributions=[],
                history=[],
                status="INSUFFICIENT_DATA",
                notes=notes or ["Unable to retrieve market price history for any holdings."],
            )

        # 2. Date alignment: align dates across all valid series
        date_sets = []
        for ticker, h_data in history_map.items():
            dates = {b.date for b in h_data.bars if b.close > 0}
            date_sets.append(dates)

        # Intersection of dates
        common_dates = sorted(list(set.intersection(*date_sets))) if date_sets else []

        if len(common_dates) < 5:
            # Union of dates with forward-fill if intersection is small
            all_dates = sorted(list(set.union(*date_sets)))
            common_dates = all_dates

        if len(common_dates) < 5:
            now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            return PerformanceMetricsResponse(
                portfolio_id=portfolio.id,
                portfolio_name=portfolio_name,
                reporting_currency=currency,
                lookback_period=period,
                start_date=now_str,
                end_date=now_str,
                observation_count=len(common_dates),
                total_return=0.0,
                annualized_return=None,
                twr=0.0,
                mwr_xirr=None,
                mwr_note="Fewer than 5 aligned trading days found.",
                contributions=[],
                history=[],
                status="INSUFFICIENT_DATA",
                notes=notes + ["Insufficient overlapping trading days to compute historical returns."],
            )

        # 3. Build price matrix & holding weights
        cost_map = {h.ticker: h.quantity * h.average_cost for h in holdings if h.ticker in history_map}
        total_active_cost = sum(cost_map.values())
        if total_active_cost <= 0:
            total_active_cost = 1.0

        weights: Dict[str, float] = {t: c / total_active_cost for t, c in cost_map.items()}

        # Build returns matrix
        holding_returns: Dict[str, np.ndarray] = {}
        holding_total_returns: Dict[str, float] = {}

        for ticker, h_data in history_map.items():
            date_price_dict = {b.date: (b.adj_close or b.close) for b in h_data.bars}
            # Extract price aligned to common_dates
            last_p = None
            aligned_prices = []
            for d in common_dates:
                p = date_price_dict.get(d)
                if p is not None and p > 0:
                    last_p = p
                aligned_prices.append(last_p if last_p is not None else 1.0)

            daily_r = calculate_daily_returns(aligned_prices)
            holding_returns[ticker] = daily_r
            if len(aligned_prices) >= 2 and aligned_prices[0] > 0:
                holding_total_returns[ticker] = calculate_total_return(aligned_prices[0], aligned_prices[-1])
            else:
                holding_total_returns[ticker] = 0.0

        # Number of return periods is len(common_dates) - 1
        num_return_periods = len(common_dates) - 1
        portfolio_daily_returns = np.zeros(num_return_periods, dtype=float)

        for ticker, daily_r in holding_returns.items():
            w = weights.get(ticker, 0.0)
            if len(daily_r) == num_return_periods:
                portfolio_daily_returns += w * daily_r

        # Cumulative portfolio returns
        cum_returns = calculate_cumulative_returns(portfolio_daily_returns)
        total_portfolio_return = float(cum_returns[-1]) if len(cum_returns) > 0 else 0.0
        annualized_return = calculate_annualized_return(total_portfolio_return, num_return_periods)

        # Performance contributions
        contributions: List[PerformanceContribution] = []
        for h in holdings:
            if h.ticker in history_map:
                w = weights.get(h.ticker, 0.0)
                tot_r = holding_total_returns.get(h.ticker, 0.0)
                contributions.append(
                    PerformanceContribution(
                        ticker=h.ticker,
                        name=h.name,
                        weight=round(w, 4),
                        total_return=round(tot_r, 4),
                        contribution=round(w * tot_r, 4),
                    )
                )

        # Build history points
        history_points: List[PerformanceHistoryPoint] = []
        for i, d in enumerate(common_dates[1:]):
            p_ret = float(portfolio_daily_returns[i])
            cum_ret = float(cum_returns[i])
            history_points.append(
                PerformanceHistoryPoint(
                    date=d,
                    portfolio_return=round(p_ret, 6),
                    cumulative_return=round(cum_ret, 6),
                    portfolio_value=round(100.0 * (1.0 + cum_ret), 2),  # Normalized to 100
                )
            )

        # 4. Money-Weighted Return (MWR / XIRR)
        # Check cash flow dates: initial investments and terminal value
        cfs: List[float] = []
        cf_dates: List[date] = []
        for h in holdings:
            if h.ticker in history_map:
                c_date = h.created_at.date() if isinstance(h.created_at, datetime) else date.today()
                cfs.append(-1.0 * (h.quantity * h.average_cost))
                cf_dates.append(c_date)

        # Terminal value at current date
        terminal_val = total_active_cost * (1.0 + total_portfolio_return)
        cfs.append(terminal_val)
        cf_dates.append(date.today())

        mwr_val: Optional[float] = None
        mwr_note = None
        # Only solve XIRR if distinct dates exist
        if len(set(cf_dates)) >= 2:
            mwr_val = calculate_xirr(cfs, cf_dates)
            if mwr_val is None:
                mwr_note = "XIRR solver did not converge with provided cash-flow dates."
        else:
            mwr_note = "Holding creation dates do not provide distinct cash-flow boundaries for XIRR."

        return PerformanceMetricsResponse(
            portfolio_id=portfolio.id,
            portfolio_name=portfolio_name,
            reporting_currency=currency,
            lookback_period=period,
            start_date=common_dates[0],
            end_date=common_dates[-1],
            observation_count=num_return_periods,
            total_return=round(total_portfolio_return, 4),
            annualized_return=annualized_return,
            twr=round(total_portfolio_return, 4),  # TWR matches compound product over pure asset series
            mwr_xirr=mwr_val,
            mwr_note=mwr_note,
            contributions=contributions,
            history=history_points,
            status="VALID",
            notes=notes,
        )


_perf_engine: Optional[PerformanceEngine] = None


def get_performance_engine() -> PerformanceEngine:
    global _perf_engine
    if _perf_engine is None:
        _perf_engine = PerformanceEngine()
    return _perf_engine
