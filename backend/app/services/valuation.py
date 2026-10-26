"""
FolioPulse AI — Portfolio Valuation Engine

Calculates:
- Cost basis = quantity × average_cost (never overwritten)
- Market value = quantity × latest validated market price (currency-converted if needed)
- Unrealized P&L = market value - cost basis
- Unrealized P&L % = (unrealized P&L / cost basis) × 100
- Allocation % = (holding market value / total portfolio market value) × 100
- Day P&L = quantity × day_change (currency-converted)

Handles multi-currency conversions using real FX rates.
Never fabricates prices or silences failures.
"""
import logging
from datetime import datetime, timezone
from typing import Optional

from app.models.user import Portfolio, Holding
from app.schemas.valuation import HoldingValuation, PortfolioValuationResponse
from app.services.market_data.service import MarketDataService, get_market_data_service

logger = logging.getLogger(__name__)


class PortfolioValuationService:
    """Computes comprehensive portfolio valuations."""

    def __init__(self, market_data_service: Optional[MarketDataService] = None):
        self.market_data = market_data_service or get_market_data_service()

    async def value_portfolio(
        self, portfolio: Portfolio, force_refresh: bool = False
    ) -> PortfolioValuationResponse:
        """Calculate market valuation for a portfolio and its active holdings."""
        holdings: list[Holding] = portfolio.holdings or []
        reporting_currency = portfolio.currency.upper()
        now_utc = datetime.now(timezone.utc)

        if not holdings:
            return PortfolioValuationResponse(
                portfolio_id=portfolio.id,
                portfolio_name=portfolio.name,
                reporting_currency=reporting_currency,
                total_cost_basis=0.0,
                total_market_value=0.0,
                total_unrealized_pnl=0.0,
                total_unrealized_pnl_percent=0.0,
                day_pnl=0.0,
                holdings_count=0,
                valued_holdings_count=0,
                valuation_complete=True,
                as_of=now_utc,
                holdings=[],
            )

        # 1. Fetch batch quotes
        tickers = [h.ticker for h in holdings]
        quotes = await self.market_data.get_quotes_batch(tickers, force_refresh=force_refresh)

        total_cost_basis = 0.0
        total_market_value = 0.0
        total_day_pnl = 0.0
        valued_count = 0
        holding_valuations: list[HoldingValuation] = []

        for h in holdings:
            cost_basis = round(h.quantity * h.average_cost, 2)
            total_cost_basis += cost_basis

            quote = quotes.get(h.ticker)
            if quote is None:
                holding_valuations.append(
                    HoldingValuation(
                        holding_id=h.id,
                        ticker=h.ticker,
                        name=h.name,
                        asset_class=h.asset_class,
                        sector=h.sector,
                        quantity=h.quantity,
                        average_cost=h.average_cost,
                        cost_basis=cost_basis,
                        data_status="UNPRICED",
                        status_note="Market quote currently unavailable from providers",
                    )
                )
                continue

            # Check currency conversion requirement
            quote_currency = quote.currency.upper()
            fx_rate = 1.0
            conversion_failed = False
            if quote_currency != reporting_currency:
                try:
                    fx_rate = await self.market_data.get_fx_rate(quote_currency, reporting_currency)
                except Exception as e:
                    logger.error("FX conversion failure for %s (%s -> %s): %s", h.ticker, quote_currency, reporting_currency, e)
                    conversion_failed = True

            if conversion_failed:
                holding_valuations.append(
                    HoldingValuation(
                        holding_id=h.id,
                        ticker=h.ticker,
                        name=h.name,
                        asset_class=h.asset_class,
                        sector=h.sector,
                        quantity=h.quantity,
                        average_cost=h.average_cost,
                        cost_basis=cost_basis,
                        market_price=quote.price,
                        quote_currency=quote_currency,
                        data_status="CONVERSION_FAILED",
                        status_note=f"Failed to convert from {quote_currency} to {reporting_currency}",
                    )
                )
                continue

            # Valid price in reporting currency
            market_price_in_rep_curr = quote.price * fx_rate
            market_val = round(h.quantity * market_price_in_rep_curr, 2)
            unrealized_pnl = round(market_val - cost_basis, 2)
            unrealized_pnl_pct = (
                round((unrealized_pnl / cost_basis) * 100, 2) if cost_basis > 0 else 0.0
            )

            day_pnl_item: Optional[float] = None
            if quote.change is not None:
                day_pnl_item = round(h.quantity * quote.change * fx_rate, 2)
                total_day_pnl += day_pnl_item

            total_market_value += market_val
            valued_count += 1

            holding_valuations.append(
                HoldingValuation(
                    holding_id=h.id,
                    ticker=h.ticker,
                    name=h.name,
                    asset_class=h.asset_class,
                    sector=h.sector,
                    quantity=h.quantity,
                    average_cost=h.average_cost,
                    cost_basis=cost_basis,
                    market_price=round(quote.price, 4),
                    quote_currency=quote_currency,
                    market_value=market_val,
                    unrealized_pnl=unrealized_pnl,
                    unrealized_pnl_percent=unrealized_pnl_pct,
                    day_change=round(quote.change, 4) if quote.change else None,
                    day_change_percent=round(quote.change_percent, 2) if quote.change_percent else None,
                    price_timestamp=quote.timestamp,
                    data_status=quote.status,
                    status_note=f"Provider: {quote.provider}",
                )
            )

        # 2. Compute allocation percentages if market value exists
        if total_market_value > 0:
            for hv in holding_valuations:
                if hv.market_value is not None:
                    hv.allocation_percent = round((hv.market_value / total_market_value) * 100, 2)

        # 3. Aggregate totals
        total_unrealized_pnl = round(total_market_value - total_cost_basis, 2)
        total_unrealized_pnl_pct = (
            round((total_unrealized_pnl / total_cost_basis) * 100, 2)
            if total_cost_basis > 0
            else 0.0
        )
        valuation_complete = valued_count == len(holdings)

        return PortfolioValuationResponse(
            portfolio_id=portfolio.id,
            portfolio_name=portfolio.name,
            reporting_currency=reporting_currency,
            total_cost_basis=round(total_cost_basis, 2),
            total_market_value=round(total_market_value, 2) if valued_count > 0 else None,
            total_unrealized_pnl=total_unrealized_pnl if valued_count > 0 else None,
            total_unrealized_pnl_percent=total_unrealized_pnl_pct if valued_count > 0 else None,
            day_pnl=round(total_day_pnl, 2) if valued_count > 0 else None,
            holdings_count=len(holdings),
            valued_holdings_count=valued_count,
            valuation_complete=valuation_complete,
            as_of=now_utc,
            holdings=holding_valuations,
        )


_valuation_service: Optional[PortfolioValuationService] = None


def get_valuation_service() -> PortfolioValuationService:
    global _valuation_service
    if _valuation_service is None:
        _valuation_service = PortfolioValuationService()
    return _valuation_service
