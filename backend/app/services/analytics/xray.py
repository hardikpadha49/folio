"""
FolioPulse AI — Portfolio X-Ray Analytics Engine

Provides institutional-grade asset allocation and breakdown:
- Asset Class Allocation (equity, debt, etf, commodity, reit, cash)
- Economic Sector Allocation
- Top holdings concentration ranking
- Foreign currency exposure
"""
import logging
from typing import Dict, List, Optional

from app.models.user import Portfolio, Holding
from app.schemas.analytics import (
    XRayResponse,
    AssetClassAllocation,
    SectorAllocation,
)
from app.services.valuation import PortfolioValuationService, get_valuation_service

logger = logging.getLogger(__name__)


class XRayEngine:
    """Computes multidimensional portfolio exposure and allocation x-rays."""

    def __init__(self, valuation_service: Optional[PortfolioValuationService] = None):
        self.valuation_service = valuation_service or get_valuation_service()

    async def generate_xray(
        self, portfolio: Portfolio, force_refresh: bool = False
    ) -> XRayResponse:
        valuation = await self.valuation_service.value_portfolio(
            portfolio, force_refresh=force_refresh
        )

        total_market_val = valuation.total_market_value or valuation.total_cost_basis or 1.0
        total_cost = valuation.total_cost_basis

        # 1. Group by Asset Class
        ac_map: Dict[str, Dict[str, float]] = {}
        # 2. Group by Sector
        sec_map: Dict[str, Dict[str, float]] = {}
        # 3. Currency exposure
        curr_map: Dict[str, float] = {}

        for hv in valuation.holdings:
            ac = hv.asset_class.lower()
            sec = (hv.sector or "Unclassified").strip()
            curr = (hv.quote_currency or portfolio.currency).upper()

            val = hv.market_value if (hv.market_value is not None and hv.market_value > 0) else hv.cost_basis
            cost = hv.cost_basis

            if ac not in ac_map:
                ac_map[ac] = {"cost": 0.0, "market": 0.0}
            ac_map[ac]["cost"] += cost
            ac_map[ac]["market"] += val

            if sec not in sec_map:
                sec_map[sec] = {"cost": 0.0, "market": 0.0}
            sec_map[sec]["cost"] += cost
            sec_map[sec]["market"] += val

            curr_map[curr] = curr_map.get(curr, 0.0) + val

        asset_classes = [
            AssetClassAllocation(
                asset_class=ac.capitalize(),
                cost_basis=round(vals["cost"], 2),
                market_value=round(vals["market"], 2),
                allocation_percent=round((vals["market"] / total_market_val) * 100, 2),
            )
            for ac, vals in sorted(ac_map.items(), key=lambda x: x[1]["market"], reverse=True)
        ]

        sectors = [
            SectorAllocation(
                sector=sec,
                cost_basis=round(vals["cost"], 2),
                market_value=round(vals["market"], 2),
                allocation_percent=round((vals["market"] / total_market_val) * 100, 2),
            )
            for sec, vals in sorted(sec_map.items(), key=lambda x: x[1]["market"], reverse=True)
        ]

        # Top holdings sorted by market value (or cost basis)
        sorted_holdings = sorted(
            valuation.holdings,
            key=lambda h: (h.market_value if h.market_value is not None else h.cost_basis),
            reverse=True,
        )
        top_holdings = [
            {
                "ticker": h.ticker,
                "name": h.name or h.ticker,
                "allocation_percent": h.allocation_percent
                or round(((h.market_value or h.cost_basis) / total_market_val) * 100, 2),
                "market_value": h.market_value if h.market_value is not None else h.cost_basis,
            }
            for h in sorted_holdings[:10]
        ]

        currency_exposure = {
            c: round((amt / total_market_val) * 100, 2) for c, amt in curr_map.items()
        }

        return XRayResponse(
            portfolio_id=portfolio.id,
            reporting_currency=portfolio.currency.upper(),
            total_cost_basis=round(total_cost, 2),
            total_market_value=round(total_market_val, 2),
            asset_class_allocation=asset_classes,
            sector_allocation=sectors,
            top_holdings=top_holdings,
            currency_exposure=currency_exposure,
        )


_xray_engine: Optional[XRayEngine] = None


def get_xray_engine() -> XRayEngine:
    global _xray_engine
    if _xray_engine is None:
        _xray_engine = XRayEngine()
    return _xray_engine
