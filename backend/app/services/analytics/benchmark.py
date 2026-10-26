"""
FolioPulse AI — Benchmark Comparison Engine

Compares portfolio historical performance against major market benchmarks:
- Indian benchmarks: NIFTY 50 (^NSEI), BSE SENSEX (^BSESN)
- US benchmarks: S&P 500 (^GSPC), NASDAQ 100 (^NDX)

Calculates:
- Aligned cumulative & annualized return series
- Excess return relative to benchmark
- Beta (systematic market risk factor)
- Jensen's Alpha (annualized risk-adjusted excess performance)
- Annualized Tracking Error
- Information Ratio (IR = Excess Return / Tracking Error)
- Normalized comparative performance curves indexed to 100
"""
import logging
import math
from typing import Dict, List, Optional
import numpy as np

from app.models.user import Portfolio
from app.schemas.analytics import (
    BenchmarkComparisonResponse,
    PerformanceHistoryPoint,
)
from app.services.analytics.math_utils import (
    calculate_daily_returns,
    calculate_cumulative_returns,
    calculate_annualized_return,
    calculate_annualized_volatility,
    calculate_sharpe_ratio,
    calculate_drawdown_series,
    TRADING_DAYS_PER_YEAR,
)
from app.services.analytics.performance import PerformanceEngine, get_performance_engine
from app.services.market_data.service import MarketDataService, get_market_data_service
from app.services.market_data.base import HistoricalData

logger = logging.getLogger(__name__)

BENCHMARK_NAMES = {
    "^NSEI": "NIFTY 50",
    "^BSESN": "BSE SENSEX",
    "^GSPC": "S&P 500",
    "^NDX": "NASDAQ 100",
}


class BenchmarkEngine:
    """Compares portfolios against market index benchmarks."""

    def __init__(
        self,
        performance_engine: Optional[PerformanceEngine] = None,
        market_data_service: Optional[MarketDataService] = None,
    ):
        self.perf_engine = performance_engine or get_performance_engine()
        self.market_data = market_data_service or get_market_data_service()

    async def compare_benchmark(
        self,
        portfolio: Portfolio,
        benchmark_symbol: Optional[str] = None,
        period: str = "1y",
        risk_free_rate: Optional[float] = None,
        custom_history: Optional[Dict[str, HistoricalData]] = None,
    ) -> BenchmarkComparisonResponse:
        currency = portfolio.currency.upper()

        # Select sensible benchmark based on portfolio currency if not specified
        if not benchmark_symbol:
            benchmark_symbol = "^NSEI" if currency == "INR" else "^GSPC"
        benchmark_symbol = benchmark_symbol.strip().upper()
        benchmark_name = BENCHMARK_NAMES.get(benchmark_symbol, benchmark_symbol)

        if risk_free_rate is None:
            risk_free_rate = 0.068 if currency == "INR" else 0.042

        # 1. Fetch portfolio performance
        perf = await self.perf_engine.calculate_performance(
            portfolio, period=period, custom_history=custom_history
        )

        if perf.status != "VALID" or perf.observation_count < 5:
            return BenchmarkComparisonResponse(
                portfolio_id=portfolio.id,
                benchmark_symbol=benchmark_symbol,
                benchmark_name=benchmark_name,
                lookback_period=period,
                observation_count=0,
                portfolio_total_return=0.0,
                benchmark_total_return=0.0,
                portfolio_annualized_return=None,
                benchmark_annualized_return=None,
                excess_return=0.0,
                beta=None,
                alpha=None,
                tracking_error=None,
                information_ratio=None,
                portfolio_volatility=0.0,
                benchmark_volatility=0.0,
                portfolio_max_drawdown=0.0,
                benchmark_max_drawdown=0.0,
                portfolio_sharpe=None,
                benchmark_sharpe=None,
                history=[],
                status="INSUFFICIENT_DATA",
                notes=perf.notes or ["Insufficient portfolio history for benchmark comparison."],
            )

        # 2. Fetch benchmark historical data
        b_hist: Optional[HistoricalData] = None
        if custom_history and benchmark_symbol in custom_history:
            b_hist = custom_history[benchmark_symbol]
        else:
            b_hist = await self.market_data.get_historical(benchmark_symbol, period=period, interval="1d")

        if not b_hist or len(b_hist.bars) < 5:
            return BenchmarkComparisonResponse(
                portfolio_id=portfolio.id,
                benchmark_symbol=benchmark_symbol,
                benchmark_name=benchmark_name,
                lookback_period=period,
                observation_count=0,
                portfolio_total_return=perf.total_return,
                benchmark_total_return=0.0,
                portfolio_annualized_return=perf.annualized_return,
                benchmark_annualized_return=None,
                excess_return=0.0,
                beta=None,
                alpha=None,
                tracking_error=None,
                information_ratio=None,
                portfolio_volatility=0.0,
                benchmark_volatility=0.0,
                portfolio_max_drawdown=0.0,
                benchmark_max_drawdown=0.0,
                portfolio_sharpe=None,
                benchmark_sharpe=None,
                history=[],
                status="BENCHMARK_UNAVAILABLE",
                notes=[f"Unable to retrieve market price history for benchmark '{benchmark_symbol}'."],
            )

        # 3. Align portfolio points and benchmark prices by date
        b_date_price = {b.date: (b.adj_close or b.close) for b in b_hist.bars if b.close > 0}
        p_history_dict = {pt.date: pt for pt in perf.history}

        aligned_dates = sorted(list(set(b_date_price.keys()).intersection(set(p_history_dict.keys()))))

        if len(aligned_dates) < 5:
            return BenchmarkComparisonResponse(
                portfolio_id=portfolio.id,
                benchmark_symbol=benchmark_symbol,
                benchmark_name=benchmark_name,
                lookback_period=period,
                observation_count=len(aligned_dates),
                portfolio_total_return=perf.total_return,
                benchmark_total_return=0.0,
                portfolio_annualized_return=perf.annualized_return,
                benchmark_annualized_return=None,
                excess_return=0.0,
                beta=None,
                alpha=None,
                tracking_error=None,
                information_ratio=None,
                portfolio_volatility=0.0,
                benchmark_volatility=0.0,
                portfolio_max_drawdown=0.0,
                benchmark_max_drawdown=0.0,
                portfolio_sharpe=None,
                benchmark_sharpe=None,
                history=[],
                status="INSUFFICIENT_DATA",
                notes=["Fewer than 5 overlapping trading dates between portfolio and benchmark."],
            )

        # Extract aligned return series
        p_rets = np.array([p_history_dict[d].portfolio_return for d in aligned_dates], dtype=float)
        b_prices = [b_date_price[d] for d in aligned_dates]
        b_rets = calculate_daily_returns(b_prices)

        # Truncate first portfolio return so lengths align to b_rets (len - 1)
        p_rets_aligned = p_rets[1:]
        aligned_dates_pts = aligned_dates[1:]

        # Cumulative returns
        p_cum = calculate_cumulative_returns(p_rets_aligned)
        b_cum = calculate_cumulative_returns(b_rets)

        n_obs = len(b_rets)
        p_tot = float(p_cum[-1]) if len(p_cum) > 0 else 0.0
        b_tot = float(b_cum[-1]) if len(b_cum) > 0 else 0.0

        p_ann = calculate_annualized_return(p_tot, n_obs)
        b_ann = calculate_annualized_return(b_tot, n_obs)

        excess_ret = round((p_ann or p_tot) - (b_ann or b_tot), 4)

        # Volatility & Drawdown
        p_vol = calculate_annualized_volatility(p_rets_aligned)
        b_vol = calculate_annualized_volatility(b_rets)

        _, p_max_dd = calculate_drawdown_series(1.0 + p_cum)
        _, b_max_dd = calculate_drawdown_series(1.0 + b_cum)

        p_sharpe = calculate_sharpe_ratio(p_ann, p_vol, risk_free_rate=risk_free_rate)
        b_sharpe = calculate_sharpe_ratio(b_ann, b_vol, risk_free_rate=risk_free_rate)

        # Beta: Cov(R_p, R_b) / Var(R_b)
        b_var = float(np.var(b_rets, ddof=1))
        beta: Optional[float] = None
        alpha: Optional[float] = None
        track_err: Optional[float] = None
        info_ratio: Optional[float] = None

        if b_var > 1e-8:
            cov = float(np.cov(p_rets_aligned, b_rets)[0, 1])
            beta = round(cov / b_var, 4)

            # Jensen's Alpha: R_p_ann - (R_f + Beta * (R_b_ann - R_f))
            if p_ann is not None and b_ann is not None and beta is not None:
                expected_ret = risk_free_rate + beta * (b_ann - risk_free_rate)
                alpha = round(p_ann - expected_ret, 4)

        # Tracking Error: std(R_p - R_b) * sqrt(252)
        diff_rets = p_rets_aligned - b_rets
        if len(diff_rets) >= 2:
            te_sample = float(np.std(diff_rets, ddof=1)) * math.sqrt(TRADING_DAYS_PER_YEAR)
            track_err = round(te_sample, 4)
            if track_err > 1e-4:
                info_ratio = round(excess_ret / track_err, 4)

        # Normalized history points
        history_points: List[PerformanceHistoryPoint] = []
        for i, d in enumerate(aligned_dates_pts):
            history_points.append(
                PerformanceHistoryPoint(
                    date=d,
                    portfolio_return=round(float(p_rets_aligned[i]), 6),
                    cumulative_return=round(float(p_cum[i]), 6),
                    portfolio_value=round(100.0 * (1.0 + float(p_cum[i])), 2),
                    benchmark_return=round(float(b_rets[i]), 6),
                    benchmark_cumulative=round(float(b_cum[i]), 6),
                )
            )

        return BenchmarkComparisonResponse(
            portfolio_id=portfolio.id,
            benchmark_symbol=benchmark_symbol,
            benchmark_name=benchmark_name,
            lookback_period=period,
            observation_count=n_obs,
            portfolio_total_return=round(p_tot, 4),
            benchmark_total_return=round(b_tot, 4),
            portfolio_annualized_return=p_ann,
            benchmark_annualized_return=b_ann,
            excess_return=excess_ret,
            beta=beta,
            alpha=alpha,
            tracking_error=track_err,
            information_ratio=info_ratio,
            portfolio_volatility=p_vol,
            benchmark_volatility=b_vol,
            portfolio_max_drawdown=p_max_dd,
            benchmark_max_drawdown=b_max_dd,
            portfolio_sharpe=p_sharpe,
            benchmark_sharpe=b_sharpe,
            history=history_points,
            status="VALID",
            notes=[],
        )


_bench_engine: Optional[BenchmarkEngine] = None


def get_benchmark_engine() -> BenchmarkEngine:
    global _bench_engine
    if _bench_engine is None:
        _bench_engine = BenchmarkEngine()
    return _bench_engine
