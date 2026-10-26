"""
FolioPulse AI — Portfolio Risk Analytics Engine

Calculates:
- Annualized sample volatility & downside semi-deviation
- Peak-to-trough Maximum Drawdown
- Sharpe and Sortino ratios with configurable risk-free rate
- Historical Value at Risk (VaR 95%, 99%)
- Historical Conditional Value at Risk (CVaR 95%, 99%)
- Herfindahl-Hirschman concentration index (HHI) & Effective N
- Pairwise correlation matrix across holdings
- Marginal and percent risk contribution per asset
"""
import logging
import math
from typing import Dict, List, Optional
import numpy as np

from app.models.user import Portfolio, Holding
from app.schemas.analytics import (
    RiskMetricsResponse,
    ConcentrationMetrics,
    RiskContribution,
)
from app.services.analytics.math_utils import (
    calculate_daily_returns,
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
    TRADING_DAYS_PER_YEAR,
)
from app.services.market_data.service import MarketDataService, get_market_data_service
from app.services.market_data.base import HistoricalData

logger = logging.getLogger(__name__)


class RiskEngine:
    """Computes comprehensive portfolio risk metrics."""

    def __init__(self, market_data_service: Optional[MarketDataService] = None):
        self.market_data = market_data_service or get_market_data_service()

    async def calculate_risk(
        self,
        portfolio: Portfolio,
        period: str = "1y",
        risk_free_rate: Optional[float] = None,
        custom_history: Optional[Dict[str, HistoricalData]] = None,
    ) -> RiskMetricsResponse:
        holdings: List[Holding] = portfolio.holdings or []
        portfolio_name = portfolio.name
        currency = portfolio.currency.upper()

        # Configurable default risk-free rate: 6.8% for INR (Indian 10Y G-Sec), 4.2% for USD
        if risk_free_rate is None:
            risk_free_rate = 0.068 if currency == "INR" else 0.042

        # 1. Weights based on holding cost basis
        cost_map = {h.ticker: h.quantity * h.average_cost for h in holdings}
        total_cost = sum(cost_map.values()) if cost_map else 0.0
        weights_all = [c / total_cost for c in cost_map.values()] if total_cost > 0 else []

        # Sort weights descending for Top-N concentration
        sorted_weights = sorted(weights_all, reverse=True)
        top_1 = round(sorted_weights[0] * 100, 2) if len(sorted_weights) >= 1 else 0.0
        top_3 = round(sum(sorted_weights[:3]) * 100, 2) if len(sorted_weights) >= 1 else 0.0
        top_5 = round(sum(sorted_weights[:5]) * 100, 2) if len(sorted_weights) >= 1 else 0.0

        concentration = ConcentrationMetrics(
            hhi=calculate_hhi(weights_all),
            effective_n=calculate_effective_n(weights_all),
            top_1_concentration=top_1,
            top_3_concentration=top_3,
            top_5_concentration=top_5,
        )

        if not holdings:
            return RiskMetricsResponse(
                portfolio_id=portfolio.id,
                portfolio_name=portfolio_name,
                lookback_period=period,
                observation_count=0,
                annualized_volatility=0.0,
                downside_deviation=0.0,
                max_drawdown=0.0,
                sharpe_ratio=None,
                sortino_ratio=None,
                risk_free_rate=risk_free_rate,
                var_95=None,
                var_99=None,
                cvar_95=None,
                cvar_99=None,
                concentration=concentration,
                correlation_matrix={},
                risk_contributions=[],
                status="EMPTY",
                notes=["Portfolio has no holdings."],
            )

        # 2. Fetch historical series
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
                f"Historical data unavailable for: {', '.join(missing_tickers)}. Risk calculated on available assets."
            )

        if not history_map:
            return RiskMetricsResponse(
                portfolio_id=portfolio.id,
                portfolio_name=portfolio_name,
                lookback_period=period,
                observation_count=0,
                annualized_volatility=0.0,
                downside_deviation=0.0,
                max_drawdown=0.0,
                sharpe_ratio=None,
                sortino_ratio=None,
                risk_free_rate=risk_free_rate,
                var_95=None,
                var_99=None,
                cvar_95=None,
                cvar_99=None,
                concentration=concentration,
                correlation_matrix={},
                risk_contributions=[],
                status="INSUFFICIENT_DATA",
                notes=notes or ["Unable to retrieve market price history."],
            )

        # 3. Align dates
        date_sets = [
            {b.date for b in h_data.bars if b.close > 0}
            for h_data in history_map.values()
        ]
        common_dates = sorted(list(set.intersection(*date_sets))) if date_sets else []
        if len(common_dates) < 5:
            common_dates = sorted(list(set.union(*date_sets)))

        if len(common_dates) < 5:
            return RiskMetricsResponse(
                portfolio_id=portfolio.id,
                portfolio_name=portfolio_name,
                lookback_period=period,
                observation_count=len(common_dates),
                annualized_volatility=0.0,
                downside_deviation=0.0,
                max_drawdown=0.0,
                sharpe_ratio=None,
                sortino_ratio=None,
                risk_free_rate=risk_free_rate,
                var_95=None,
                var_99=None,
                cvar_95=None,
                cvar_99=None,
                concentration=concentration,
                correlation_matrix={},
                risk_contributions=[],
                status="INSUFFICIENT_DATA",
                notes=notes + ["Fewer than 5 overlapping trading days."],
            )

        # 4. Returns matrix & aligned prices
        active_tickers = list(history_map.keys())
        active_costs = {t: cost_map.get(t, 1.0) for t in active_tickers}
        tot_active_cost = sum(active_costs.values()) or 1.0
        w_dict = {t: c / tot_active_cost for t, c in active_costs.items()}

        returns_by_ticker: Dict[str, np.ndarray] = {}
        for ticker in active_tickers:
            h_data = history_map[ticker]
            date_price = {b.date: (b.adj_close or b.close) for b in h_data.bars}
            last_p = None
            aligned_p = []
            for d in common_dates:
                p = date_price.get(d)
                if p is not None and p > 0:
                    last_p = p
                aligned_p.append(last_p if last_p is not None else 1.0)
            returns_by_ticker[ticker] = calculate_daily_returns(aligned_p)

        n_obs = len(common_dates) - 1
        portfolio_returns = np.zeros(n_obs, dtype=float)
        for ticker in active_tickers:
            portfolio_returns += w_dict[ticker] * returns_by_ticker[ticker]

        # 5. Core Volatility & Drawdown
        ann_vol = calculate_annualized_volatility(portfolio_returns)
        mar_daily = risk_free_rate / TRADING_DAYS_PER_YEAR
        downside_dev = calculate_downside_deviation(portfolio_returns, mar_daily=mar_daily)

        wealth_index = np.cumprod(1.0 + portfolio_returns)
        _, max_dd = calculate_drawdown_series(wealth_index)

        # Total & Annualized Return for Sharpe/Sortino
        total_ret = float(wealth_index[-1] - 1.0) if len(wealth_index) > 0 else 0.0
        ann_ret = calculate_annualized_return(total_ret, n_obs)

        sharpe = calculate_sharpe_ratio(ann_ret, ann_vol, risk_free_rate=risk_free_rate)
        sortino = calculate_sortino_ratio(ann_ret, downside_dev, risk_free_rate=risk_free_rate)

        # 6. VaR and CVaR (95% and 99%)
        var_95 = calculate_historical_var(portfolio_returns, confidence_level=0.95)
        var_99 = calculate_historical_var(portfolio_returns, confidence_level=0.99)
        cvar_95 = calculate_historical_cvar(portfolio_returns, confidence_level=0.95)
        cvar_99 = calculate_historical_cvar(portfolio_returns, confidence_level=0.99)

        # 7. Correlation Matrix
        corr_matrix: Dict[str, Dict[str, float]] = {}
        for t1 in active_tickers:
            corr_matrix[t1] = {}
            for t2 in active_tickers:
                if t1 == t2:
                    corr_matrix[t1][t2] = 1.0
                else:
                    r1 = returns_by_ticker[t1]
                    r2 = returns_by_ticker[t2]
                    std1 = np.std(r1)
                    std2 = np.std(r2)
                    if std1 > 1e-6 and std2 > 1e-6:
                        c_val = float(np.corrcoef(r1, r2)[0, 1])
                        corr_matrix[t1][t2] = round(c_val, 4) if not math.isnan(c_val) else 0.0
                    else:
                        corr_matrix[t1][t2] = 0.0

        # 8. Marginal Risk Contributions
        # MRC_i = w_i * Cov(R_i, R_p) / Var(R_p)
        port_var = float(np.var(portfolio_returns, ddof=1))
        risk_contributions: List[RiskContribution] = []

        for ticker in active_tickers:
            r_asset = returns_by_ticker[ticker]
            asset_vol = calculate_annualized_volatility(r_asset)
            w = w_dict[ticker]
            if port_var > 1e-8:
                cov_val = float(np.cov(r_asset, portfolio_returns)[0, 1])
                mrc = (cov_val / math.sqrt(port_var)) * math.sqrt(TRADING_DAYS_PER_YEAR)
                pct_contrib = (w * cov_val / port_var) * 100.0
            else:
                mrc = 0.0
                pct_contrib = w * 100.0

            risk_contributions.append(
                RiskContribution(
                    ticker=ticker,
                    weight=round(w, 4),
                    annualized_volatility=round(asset_vol, 4),
                    marginal_risk_contribution=round(float(mrc), 4),
                    percent_contribution=round(float(pct_contrib), 2),
                )
            )

        return RiskMetricsResponse(
            portfolio_id=portfolio.id,
            portfolio_name=portfolio_name,
            lookback_period=period,
            observation_count=n_obs,
            annualized_volatility=ann_vol,
            downside_deviation=downside_dev,
            max_drawdown=max_dd,
            sharpe_ratio=sharpe,
            sortino_ratio=sortino,
            risk_free_rate=risk_free_rate,
            var_95=var_95,
            var_99=var_99,
            cvar_95=cvar_95,
            cvar_99=cvar_99,
            concentration=concentration,
            correlation_matrix=corr_matrix,
            risk_contributions=risk_contributions,
            status="VALID",
            notes=notes,
        )


_risk_engine: Optional[RiskEngine] = None


def get_risk_engine() -> RiskEngine:
    global _risk_engine
    if _risk_engine is None:
        _risk_engine = RiskEngine()
    return _risk_engine
