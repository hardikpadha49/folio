"""FolioPulse AI — Financial Analytics Services Package"""
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
from app.services.analytics.performance import PerformanceEngine, get_performance_engine
from app.services.analytics.risk import RiskEngine, get_risk_engine
from app.services.analytics.diversification import (
    DiversificationEngine,
    get_diversification_engine,
)
from app.services.analytics.health import HealthScoreEngine, get_health_score_engine
from app.services.analytics.benchmark import BenchmarkEngine, get_benchmark_engine
from app.services.analytics.xray import XRayEngine, get_xray_engine

__all__ = [
    "calculate_daily_returns",
    "calculate_cumulative_returns",
    "calculate_total_return",
    "calculate_annualized_return",
    "calculate_annualized_volatility",
    "calculate_downside_deviation",
    "calculate_sharpe_ratio",
    "calculate_sortino_ratio",
    "calculate_drawdown_series",
    "calculate_historical_var",
    "calculate_historical_cvar",
    "calculate_hhi",
    "calculate_effective_n",
    "calculate_shannon_entropy",
    "calculate_xirr",
    "PerformanceEngine",
    "get_performance_engine",
    "RiskEngine",
    "get_risk_engine",
    "DiversificationEngine",
    "get_diversification_engine",
    "HealthScoreEngine",
    "get_health_score_engine",
    "BenchmarkEngine",
    "get_benchmark_engine",
    "XRayEngine",
    "get_xray_engine",
]
