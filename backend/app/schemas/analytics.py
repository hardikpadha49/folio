"""
FolioPulse AI — Pydantic Schemas for Financial Analytics Engine
"""
import uuid
from datetime import datetime
from typing import Dict, List, Optional
from pydantic import BaseModel


class PerformanceContribution(BaseModel):
    ticker: str
    name: Optional[str] = None
    weight: float
    total_return: float
    contribution: float


class PerformanceHistoryPoint(BaseModel):
    date: str
    portfolio_return: float
    cumulative_return: float
    portfolio_value: Optional[float] = None
    benchmark_return: Optional[float] = None
    benchmark_cumulative: Optional[float] = None


class PerformanceMetricsResponse(BaseModel):
    portfolio_id: uuid.UUID
    portfolio_name: str
    reporting_currency: str
    lookback_period: str
    start_date: str
    end_date: str
    observation_count: int
    total_return: float
    annualized_return: Optional[float] = None
    twr: float
    mwr_xirr: Optional[float] = None
    mwr_note: Optional[str] = None
    contributions: List[PerformanceContribution]
    history: List[PerformanceHistoryPoint]
    status: str = "VALID"
    notes: List[str] = []


class ConcentrationMetrics(BaseModel):
    hhi: float
    effective_n: float
    top_1_concentration: float
    top_3_concentration: float
    top_5_concentration: float


class RiskContribution(BaseModel):
    ticker: str
    weight: float
    annualized_volatility: float
    marginal_risk_contribution: float
    percent_contribution: float


class RiskMetricsResponse(BaseModel):
    portfolio_id: uuid.UUID
    portfolio_name: str
    lookback_period: str
    observation_count: int
    annualized_volatility: float
    downside_deviation: float
    max_drawdown: float
    sharpe_ratio: Optional[float] = None
    sortino_ratio: Optional[float] = None
    risk_free_rate: float
    var_95: Optional[float] = None
    var_99: Optional[float] = None
    cvar_95: Optional[float] = None
    cvar_99: Optional[float] = None
    concentration: ConcentrationMetrics
    correlation_matrix: Dict[str, Dict[str, float]]
    risk_contributions: List[RiskContribution]
    status: str = "VALID"
    notes: List[str] = []


class DiversificationComponent(BaseModel):
    dimension: str
    score: float       # 0 - 100
    weight: float      # component weight
    metric_value: str  # human readable e.g. "Effective N: 4.8 / 5"
    description: str


class DiversificationResponse(BaseModel):
    portfolio_id: uuid.UUID
    score: float       # 0 - 100
    rating: str        # High, Moderate, Concentrated, Highly Concentrated
    components: List[DiversificationComponent]
    explanation: str


class HealthScoreComponent(BaseModel):
    factor: str
    score: float
    weight: float
    impact: str
    detail: str


class HealthScoreResponse(BaseModel):
    portfolio_id: uuid.UUID
    overall_score: float   # 0 - 100
    rating: str            # Excellent, Strong, Moderate, Fragile, Critical
    status: str            # VALID, INSUFFICIENT_DATA
    components: List[HealthScoreComponent]
    key_strengths: List[str]
    key_risks: List[str]
    disclaimer: str


class BenchmarkComparisonResponse(BaseModel):
    portfolio_id: uuid.UUID
    benchmark_symbol: str
    benchmark_name: str
    lookback_period: str
    observation_count: int
    portfolio_total_return: float
    benchmark_total_return: float
    portfolio_annualized_return: Optional[float] = None
    benchmark_annualized_return: Optional[float] = None
    excess_return: float
    beta: Optional[float] = None
    alpha: Optional[float] = None
    tracking_error: Optional[float] = None
    information_ratio: Optional[float] = None
    portfolio_volatility: float
    benchmark_volatility: float
    portfolio_max_drawdown: float
    benchmark_max_drawdown: float
    portfolio_sharpe: Optional[float] = None
    benchmark_sharpe: Optional[float] = None
    history: List[PerformanceHistoryPoint]
    status: str = "VALID"
    notes: List[str] = []


class AssetClassAllocation(BaseModel):
    asset_class: str
    cost_basis: float
    market_value: float
    allocation_percent: float


class SectorAllocation(BaseModel):
    sector: str
    cost_basis: float
    market_value: float
    allocation_percent: float


class XRayResponse(BaseModel):
    portfolio_id: uuid.UUID
    reporting_currency: str
    total_cost_basis: float
    total_market_value: float
    asset_class_allocation: List[AssetClassAllocation]
    sector_allocation: List[SectorAllocation]
    top_holdings: List[Dict[str, float]]
    currency_exposure: Dict[str, float]


class FullAnalyticsResponse(BaseModel):
    portfolio_id: uuid.UUID
    portfolio_name: str
    reporting_currency: str
    valuation_date: datetime
    performance: PerformanceMetricsResponse
    risk: RiskMetricsResponse
    diversification: DiversificationResponse
    health: HealthScoreResponse
    benchmark: Optional[BenchmarkComparisonResponse] = None
    xray: XRayResponse
