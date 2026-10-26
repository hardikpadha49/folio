"""
FolioPulse AI — Financial Analytics API Routes

Endpoints:
  GET /api/v1/portfolios/{id}/performance       — Historical returns, TWR, MWR/XIRR, contributions
  GET /api/v1/portfolios/{id}/risk              — Volatility, Sharpe, Sortino, VaR, CVaR, correlations
  GET /api/v1/portfolios/{id}/diversification   — 0-100 Diversification Index & factor breakdown
  GET /api/v1/portfolios/{id}/health            — 0-100 Portfolio Health Score & risk drivers
  GET /api/v1/portfolios/{id}/benchmark         — NIFTY 50 / S&P 500 alpha, beta, tracking error
  GET /api/v1/portfolios/{id}/xray              — Asset class, sector, currency allocation x-ray
  GET /api/v1/portfolios/{id}/analytics         — Full consolidated analytics payload
"""
import uuid
from datetime import datetime, timezone
from typing import Optional
from fastapi import APIRouter, Query, status

from app.core.dependencies import CurrentUser, DBSession
from app.core.exceptions import NotFoundError
from app.models.user import Portfolio
from app.schemas.analytics import (
    PerformanceMetricsResponse,
    RiskMetricsResponse,
    DiversificationResponse,
    HealthScoreResponse,
    BenchmarkComparisonResponse,
    XRayResponse,
    FullAnalyticsResponse,
)
from app.services.analytics import (
    get_performance_engine,
    get_risk_engine,
    get_diversification_engine,
    get_health_score_engine,
    get_benchmark_engine,
    get_xray_engine,
)

router = APIRouter(prefix="/portfolios/{portfolio_id}", tags=["Financial Analytics"])


def _get_portfolio_or_raise(portfolio_id: uuid.UUID, user_id: uuid.UUID, db) -> Portfolio:
    portfolio = db.get(Portfolio, portfolio_id)
    if portfolio is None or not portfolio.is_active or portfolio.user_id != user_id:
        raise NotFoundError("Portfolio")
    return portfolio


@router.get(
    "/performance",
    response_model=PerformanceMetricsResponse,
    summary="Get historical performance, cumulative returns, TWR and MWR/XIRR",
)
async def get_performance(
    portfolio_id: uuid.UUID,
    current_user: CurrentUser,
    db: DBSession,
    period: str = Query("1y", description="Lookback window (e.g. 1mo, 3mo, 6mo, 1y, 5y)"),
):
    portfolio = _get_portfolio_or_raise(portfolio_id, current_user.id, db)
    engine = get_performance_engine()
    return await engine.calculate_performance(portfolio, period=period)


@router.get(
    "/risk",
    response_model=RiskMetricsResponse,
    summary="Get volatility, Sharpe, Sortino, VaR, CVaR, and correlation matrix",
)
async def get_risk(
    portfolio_id: uuid.UUID,
    current_user: CurrentUser,
    db: DBSession,
    period: str = Query("1y", description="Lookback window (e.g. 1mo, 3mo, 6mo, 1y, 5y)"),
    risk_free_rate: Optional[float] = Query(None, description="Annualized risk-free rate (e.g. 0.068)"),
):
    portfolio = _get_portfolio_or_raise(portfolio_id, current_user.id, db)
    engine = get_risk_engine()
    return await engine.calculate_risk(portfolio, period=period, risk_free_rate=risk_free_rate)


@router.get(
    "/diversification",
    response_model=DiversificationResponse,
    summary="Get transparent 0-100 Diversification Index and component metrics",
)
async def get_diversification(
    portfolio_id: uuid.UUID,
    current_user: CurrentUser,
    db: DBSession,
):
    portfolio = _get_portfolio_or_raise(portfolio_id, current_user.id, db)
    engine = get_diversification_engine()
    return await engine.calculate_diversification(portfolio)


@router.get(
    "/health",
    response_model=HealthScoreResponse,
    summary="Get 0-100 Portfolio Health Score and key risk/strength drivers",
)
async def get_health(
    portfolio_id: uuid.UUID,
    current_user: CurrentUser,
    db: DBSession,
    period: str = Query("1y", description="Lookback window"),
):
    portfolio = _get_portfolio_or_raise(portfolio_id, current_user.id, db)
    engine = get_health_score_engine()
    return await engine.calculate_health(portfolio, period=period)


@router.get(
    "/benchmark",
    response_model=BenchmarkComparisonResponse,
    summary="Compare portfolio performance against market benchmarks (NIFTY 50, S&P 500)",
)
async def get_benchmark(
    portfolio_id: uuid.UUID,
    current_user: CurrentUser,
    db: DBSession,
    benchmark_symbol: Optional[str] = Query(None, description="Benchmark symbol (^NSEI, ^BSESN, ^GSPC)"),
    period: str = Query("1y", description="Lookback window"),
):
    portfolio = _get_portfolio_or_raise(portfolio_id, current_user.id, db)
    engine = get_benchmark_engine()
    return await engine.compare_benchmark(portfolio, benchmark_symbol=benchmark_symbol, period=period)


@router.get(
    "/xray",
    response_model=XRayResponse,
    summary="Get portfolio allocation x-ray by asset class, sector, and currency",
)
async def get_xray(
    portfolio_id: uuid.UUID,
    current_user: CurrentUser,
    db: DBSession,
    refresh: bool = Query(False, description="Force fresh market valuation"),
):
    portfolio = _get_portfolio_or_raise(portfolio_id, current_user.id, db)
    engine = get_xray_engine()
    return await engine.generate_xray(portfolio, force_refresh=refresh)


@router.get(
    "/analytics",
    response_model=FullAnalyticsResponse,
    summary="Get consolidated full analytics suite for portfolio dashboard",
)
async def get_full_analytics(
    portfolio_id: uuid.UUID,
    current_user: CurrentUser,
    db: DBSession,
    period: str = Query("1y", description="Lookback window"),
    benchmark_symbol: Optional[str] = Query(None, description="Benchmark symbol"),
):
    portfolio = _get_portfolio_or_raise(portfolio_id, current_user.id, db)

    perf_engine = get_performance_engine()
    risk_engine = get_risk_engine()
    div_engine = get_diversification_engine()
    health_engine = get_health_score_engine()
    bench_engine = get_benchmark_engine()
    xray_engine = get_xray_engine()

    perf = await perf_engine.calculate_performance(portfolio, period=period)
    risk = await risk_engine.calculate_risk(portfolio, period=period)
    div = await div_engine.calculate_diversification(portfolio)
    health = await health_engine.calculate_health(portfolio, period=period)
    bench = await bench_engine.compare_benchmark(portfolio, benchmark_symbol=benchmark_symbol, period=period)
    xray = await xray_engine.generate_xray(portfolio)

    return FullAnalyticsResponse(
        portfolio_id=portfolio.id,
        portfolio_name=portfolio.name,
        reporting_currency=portfolio.currency.upper(),
        valuation_date=datetime.now(timezone.utc),
        performance=perf,
        risk=risk,
        diversification=div,
        health=health,
        benchmark=bench,
        xray=xray,
    )
