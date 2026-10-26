"""
FolioPulse AI — Market Data API Routes

Endpoints:
  GET /api/v1/market/quote/{symbol}   — Fetch validated latest market quote
  GET /api/v1/market/history/{symbol} — Fetch historical OHLCV price series
"""
from typing import Optional
from fastapi import APIRouter, Query, HTTPException, status

from app.core.dependencies import CurrentUser
from app.core.exceptions import NotFoundError
from app.services.market_data.service import get_market_data_service
from app.services.market_data.base import QuoteData, HistoricalData

router = APIRouter(prefix="/market", tags=["Market Data"])


@router.get(
    "/quote/{symbol}",
    response_model=dict,
    summary="Get latest market quote for an equity/ETF symbol",
)
async def get_market_quote(
    symbol: str,
    current_user: CurrentUser,
    refresh: bool = Query(False, description="Force refresh bypass cache"),
):
    service = get_market_data_service()
    quote = await service.get_quote(symbol, force_refresh=refresh)
    if quote is None:
        raise NotFoundError(f"Market quote for symbol '{symbol}'")
    return quote.to_dict()


@router.get(
    "/history/{symbol}",
    response_model=dict,
    summary="Get historical OHLCV data for an equity/ETF symbol",
)
async def get_market_history(
    symbol: str,
    current_user: CurrentUser,
    period: str = Query("1mo", description="Historical period (e.g. 5d, 1mo, 3mo, 1y, 5y)"),
    interval: str = Query("1d", description="Data interval (e.g. 1d, 1wk)"),
    refresh: bool = Query(False, description="Force refresh bypass cache"),
):
    service = get_market_data_service()
    history = await service.get_historical(
        symbol, period=period, interval=interval, force_refresh=refresh
    )
    if history is None:
        raise NotFoundError(f"Historical data for symbol '{symbol}'")
    return history.to_dict()
