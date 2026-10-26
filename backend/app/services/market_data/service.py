"""
FolioPulse AI — Market Data Service Orchestrator

Coordinates Yahoo Finance and Alpha Vantage with:
- Intelligent provider selection & graceful fallback
- Provider-aware caching with TTL and data age tracking
- Currency exchange rate lookup (USD, INR, EUR, GBP)
- Explicit data-quality flagging (never fabricates data)
"""
import asyncio
import logging
from datetime import datetime, timezone
from typing import Optional

from app.core.cache import get_cache
from app.services.market_data.base import (
    BaseMarketDataProvider,
    QuoteData,
    HistoricalData,
)
from app.services.market_data.yahoo import YahooFinanceProvider
from app.services.market_data.alpha_vantage import AlphaVantageProvider

logger = logging.getLogger(__name__)


class MarketDataService:
    """Central market data service with caching and fallback."""

    def __init__(
        self,
        primary_provider: Optional[BaseMarketDataProvider] = None,
        secondary_provider: Optional[BaseMarketDataProvider] = None,
        quote_ttl: int = 300,        # 5 minutes
        history_ttl: int = 3600,     # 1 hour
        fx_ttl: int = 1800,          # 30 minutes
    ):
        self.primary = primary_provider or YahooFinanceProvider()
        self.secondary = secondary_provider or AlphaVantageProvider()
        self.quote_ttl = quote_ttl
        self.history_ttl = history_ttl
        self.fx_ttl = fx_ttl
        self.cache = get_cache()

    async def get_quote(
        self, symbol: str, force_refresh: bool = False
    ) -> Optional[QuoteData]:
        """
        Fetch quote for a symbol, checking cache first unless force_refresh is True.
        Attempts primary provider, then secondary fallback.
        """
        clean_symbol = symbol.strip().upper()
        cache_key = f"quote:{clean_symbol}"

        # 1. Check cache
        if not force_refresh:
            cached_raw = self.cache.get(cache_key)
            if cached_raw is not None:
                try:
                    quote = QuoteData.from_dict(cached_raw)
                    # Verify age
                    now = datetime.now(timezone.utc)
                    age_seconds = (now - quote.retrieved_at).total_seconds()
                    if age_seconds > self.quote_ttl:
                        quote.status = "STALE"
                    return quote
                except Exception as e:
                    logger.warning("Error deserializing cached quote for %s: %s", clean_symbol, e)

        # 2. Query primary provider
        quote: Optional[QuoteData] = None
        try:
            if await self.primary.is_available():
                quote = await self.primary.get_quote(clean_symbol)
        except Exception as e:
            logger.warning("Primary provider %s failed for %s: %s", self.primary.get_provider_name(), clean_symbol, e)

        # 3. Query secondary provider if primary failed
        if quote is None:
            try:
                if await self.secondary.is_available():
                    logger.info("Attempting secondary provider %s for %s", self.secondary.get_provider_name(), clean_symbol)
                    quote = await self.secondary.get_quote(clean_symbol)
                    if quote:
                        quote.status = "FALLBACK"
            except Exception as e:
                logger.warning("Secondary provider %s failed for %s: %s", self.secondary.get_provider_name(), clean_symbol, e)

        # 4. Cache if successful
        if quote is not None:
            self.cache.set(cache_key, quote.to_dict(), ttl_seconds=self.quote_ttl)

        return quote

    async def get_quotes_batch(
        self, symbols: list[str], force_refresh: bool = False
    ) -> dict[str, Optional[QuoteData]]:
        """Fetch quotes for multiple symbols concurrently."""
        unique_symbols = list({s.strip().upper() for s in symbols if s.strip()})
        tasks = [self.get_quote(sym, force_refresh=force_refresh) for sym in unique_symbols]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        batch_result: dict[str, Optional[QuoteData]] = {}
        for sym, res in zip(unique_symbols, results):
            if isinstance(res, Exception) or res is None:
                batch_result[sym] = None
            else:
                batch_result[sym] = res
        return batch_result

    async def get_historical(
        self,
        symbol: str,
        period: str = "1mo",
        interval: str = "1d",
        force_refresh: bool = False,
    ) -> Optional[HistoricalData]:
        """Fetch historical time series with caching."""
        clean_symbol = symbol.strip().upper()
        cache_key = f"hist:{clean_symbol}:{period}:{interval}"

        if not force_refresh:
            cached_raw = self.cache.get(cache_key)
            if cached_raw is not None:
                try:
                    return HistoricalData.from_dict(cached_raw)
                except Exception as e:
                    logger.warning("Error deserializing historical data for %s: %s", clean_symbol, e)

        # Primary
        hist: Optional[HistoricalData] = None
        try:
            if await self.primary.is_available():
                hist = await self.primary.get_historical(clean_symbol, period=period, interval=interval)
        except Exception as e:
            logger.warning("Primary provider historical error for %s: %s", clean_symbol, e)

        # Secondary
        if hist is None:
            try:
                if await self.secondary.is_available():
                    hist = await self.secondary.get_historical(clean_symbol, period=period, interval=interval)
            except Exception as e:
                logger.warning("Secondary provider historical error for %s: %s", clean_symbol, e)

        if hist is not None:
            self.cache.set(cache_key, hist.to_dict(), ttl_seconds=self.history_ttl)

        return hist

    async def get_fx_rate(self, from_currency: str, to_currency: str) -> float:
        """
        Get exchange rate from `from_currency` to `to_currency`.
        Returns 1.0 if currencies match.
        Never fabricates an arbitrary rate; raises ValueError if FX lookup fails.
        """
        from_c = from_currency.strip().upper()
        to_c = to_currency.strip().upper()

        if from_c == to_c:
            return 1.0

        cache_key = f"fx:{from_c}_{to_c}"
        cached_rate = self.cache.get(cache_key)
        if cached_rate is not None and isinstance(cached_rate, (int, float)):
            return float(cached_rate)

        # Direct pair lookup via yfinance (e.g. USDINR=X)
        direct_symbol = f"{from_c}{to_c}=X"
        quote = await self.get_quote(direct_symbol)
        if quote and quote.price > 0:
            rate = float(quote.price)
            self.cache.set(cache_key, rate, ttl_seconds=self.fx_ttl)
            return rate

        # Invert lookup (e.g. INRUSD=X -> 1 / rate)
        inverse_symbol = f"{to_c}{from_c}=X"
        inv_quote = await self.get_quote(inverse_symbol)
        if inv_quote and inv_quote.price > 0:
            rate = round(1.0 / float(inv_quote.price), 6)
            self.cache.set(cache_key, rate, ttl_seconds=self.fx_ttl)
            return rate

        # Standard known anchor via USD if both are non-USD (e.g. EUR to INR = EURUSD * USDINR)
        if from_c != "USD" and to_c != "USD":
            try:
                rate_from_usd = await self.get_fx_rate(from_c, "USD")
                rate_usd_to = await self.get_fx_rate("USD", to_c)
                cross_rate = round(rate_from_usd * rate_usd_to, 6)
                self.cache.set(cache_key, cross_rate, ttl_seconds=self.fx_ttl)
                return cross_rate
            except Exception as e:
                logger.error("Cross FX rate derivation failed for %s -> %s: %s", from_c, to_c, e)

        raise ValueError(
            f"Cannot determine exchange rate from {from_c} to {to_c}. Market quote unavailable."
        )


_service_instance: Optional[MarketDataService] = None


def get_market_data_service() -> MarketDataService:
    global _service_instance
    if _service_instance is None:
        _service_instance = MarketDataService()
    return _service_instance
