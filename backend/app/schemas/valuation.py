"""
FolioPulse AI — Pydantic Schemas for Portfolio Valuation
"""
import uuid
from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel


class HoldingValuation(BaseModel):
    holding_id: uuid.UUID
    ticker: str
    name: Optional[str] = None
    asset_class: str
    sector: Optional[str] = None
    quantity: float
    average_cost: float
    cost_basis: float
    market_price: Optional[float] = None
    quote_currency: Optional[str] = None
    market_value: Optional[float] = None
    unrealized_pnl: Optional[float] = None
    unrealized_pnl_percent: Optional[float] = None
    allocation_percent: Optional[float] = None
    day_change: Optional[float] = None
    day_change_percent: Optional[float] = None
    price_timestamp: Optional[datetime] = None
    data_status: str = "VALID"  # VALID, STALE, UNPRICED, CONVERSION_FAILED
    status_note: Optional[str] = None


class PortfolioValuationResponse(BaseModel):
    portfolio_id: uuid.UUID
    portfolio_name: str
    reporting_currency: str
    total_cost_basis: float
    total_market_value: Optional[float] = None
    total_unrealized_pnl: Optional[float] = None
    total_unrealized_pnl_percent: Optional[float] = None
    day_pnl: Optional[float] = None
    holdings_count: int
    valued_holdings_count: int
    valuation_complete: bool
    as_of: datetime
    holdings: List[HoldingValuation]
