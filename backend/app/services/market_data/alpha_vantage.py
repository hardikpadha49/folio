"""
FolioPulse AI — Alpha Vantage Market Data Provider (Optional Secondary Fallback)

Uses official REST endpoints with API key validation, rate-limit awareness,
and error handling. Never fabricates prices.
"""
import logging
from datetime import datetime, timezone
from typing import Optional

import httpx

from app.config import get_settings
from app.services.market_data.base import (
    BaseMarketDataProvider,
    QuoteData,
    HistoricalBar,
    HistoricalData,
)

logger = logging.getLogger(__name__)
settings = get_settings()

BASE_URL = "https://www.alphavantage.co/query"


class AlphaVantageProvider(BaseMarketDataProvider):
    """Alpha Vantage provider using official HTTP API."""

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or settings.alpha_vantage_api_key

    def get_provider_name(self) -> str:
        return "alpha_vantage"

    async def is_available(self) -> bool:
        return bool(self.api_key and len(self.api_key.strip()) > 4)

    async def get_quote(self, symbol: str) -> Optional[QuoteData]:
        if not await self.is_available():
            logger.debug("Alpha Vantage not available: missing API key.")
            return None

        # Clean symbol for Alpha Vantage (Alpha Vantage format for NSE: e.g. RELIANCE.BSE or RELIANCE.NSE)
        clean_symbol = symbol.strip().upper()
        av_symbol = clean_symbol
        if clean_symbol.endswith(".NS"):
            av_symbol = clean_symbol.replace(".NS", ".NSE")
        elif clean_symbol.endswith(".BO"):
            av_symbol = clean_symbol.replace(".BO", ".BSE")

        params = {
            "function": "GLOBAL_QUOTE",
            "symbol": av_symbol,
            "apikey": self.api_key,
        }

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(BASE_URL, params=params)
                if resp.status_code != 200:
                    logger.warning("Alpha Vantage returned HTTP %s for %s", resp.status_code, symbol)
                    return None

                data = resp.json()

                # Check rate limiting / info messages
                if "Note" in data or "Information" in data:
                    msg = data.get("Note") or data.get("Information")
                    logger.warning("Alpha Vantage limit/notice: %s", msg)
                    return None

                quote_dict = data.get("Global Quote", {})
                if not quote_dict or "05. price" not in quote_dict:
                    logger.warning("No quote returned by Alpha Vantage for %s", symbol)
                    return None

                price = float(quote_dict["05. price"])
                if price <= 0:
                    return None

                prev_close = float(quote_dict.get("08. previous close", price))
                change = float(quote_dict.get("09. change", price - prev_close))
                raw_pct = quote_dict.get("10. change percent", "0%").replace("%", "").strip()
                change_pct = float(raw_pct) if raw_pct else 0.0

                open_price = (
                    float(quote_dict["02. open"]) if "02. open" in quote_dict else None
                )
                high = float(quote_dict["03. high"]) if "03. high" in quote_dict else None
                low = float(quote_dict["04. low"]) if "04. low" in quote_dict else None
                vol_str = quote_dict.get("06. volume")
                volume = int(vol_str) if vol_str and vol_str.isdigit() else None

                currency = "INR" if symbol.endswith((".NS", ".BO")) else "USD"
                now_utc = datetime.now(timezone.utc)

                return QuoteData(
                    symbol=symbol,
                    price=round(price, 4),
                    currency=currency,
                    previous_close=round(prev_close, 4),
                    change=round(change, 4),
                    change_percent=round(change_pct, 4),
                    open=open_price,
                    high=high,
                    low=low,
                    volume=volume,
                    timestamp=now_utc,
                    retrieved_at=now_utc,
                    provider=self.get_provider_name(),
                    is_delayed=True,
                    market_state="REGULAR",
                    status="FALLBACK",
                )
        except Exception as e:
            logger.error("Alpha Vantage request failed for %s: %s", symbol, e)
            return None

    async def get_historical(
        self, symbol: str, period: str = "1mo", interval: str = "1d"
    ) -> Optional[HistoricalData]:
        if not await self.is_available():
            return None

        clean_symbol = symbol.strip().upper()
        av_symbol = clean_symbol
        if clean_symbol.endswith(".NS"):
            av_symbol = clean_symbol.replace(".NS", ".NSE")
        elif clean_symbol.endswith(".BO"):
            av_symbol = clean_symbol.replace(".BO", ".BSE")

        params = {
            "function": "TIME_SERIES_DAILY",
            "symbol": av_symbol,
            "outputsize": "compact",
            "apikey": self.api_key,
        }

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.get(BASE_URL, params=params)
                if resp.status_code != 200:
                    return None

                data = resp.json()
                if "Note" in data or "Information" in data:
                    return None

                ts_key = next((k for k in data if "Time Series" in k), None)
                if not ts_key:
                    return None

                time_series = data[ts_key]
                bars = []
                for date_str, values in sorted(time_series.items()):
                    c_val = float(values.get("4. close", 0.0))
                    bars.append(
                        HistoricalBar(
                            date=date_str,
                            open=float(values.get("1. open", c_val)),
                            high=float(values.get("2. high", c_val)),
                            low=float(values.get("3. low", c_val)),
                            close=c_val,
                            volume=int(values.get("5. volume", 0)),
                            adj_close=c_val,
                        )
                    )

                currency = "INR" if symbol.endswith((".NS", ".BO")) else "USD"
                return HistoricalData(
                    symbol=symbol,
                    currency=currency,
                    provider=self.get_provider_name(),
                    bars=bars,
                    retrieved_at=datetime.now(timezone.utc),
                )
        except Exception as e:
            logger.error("Alpha Vantage historical fetch error for %s: %s", symbol, e)
            return None
