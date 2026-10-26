"""
FolioPulse AI — Yahoo Finance Market Data Provider
Uses yfinance for non-commercial equity and ETF quote/history retrieval.
Handles Indian (.NS, .BO), US, and global exchange symbols with strict validation.
"""
import asyncio
import logging
import math
from datetime import datetime, timezone
from typing import Optional

import pandas as pd
import yfinance as yf

from app.services.market_data.base import (
    BaseMarketDataProvider,
    QuoteData,
    HistoricalBar,
    HistoricalData,
)

logger = logging.getLogger(__name__)


def _sanitize_symbol(symbol: str) -> str:
    """Normalize symbol to uppercase trimmed string."""
    return symbol.strip().upper()


class YahooFinanceProvider(BaseMarketDataProvider):
    """Yahoo Finance provider implementation."""

    def get_provider_name(self) -> str:
        return "yahoo_finance"

    async def is_available(self) -> bool:
        # yfinance is a local client library requiring internet access
        return True

    async def get_quote(self, symbol: str) -> Optional[QuoteData]:
        clean_symbol = _sanitize_symbol(symbol)
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self._sync_get_quote, clean_symbol)

    def _sync_get_quote(self, symbol: str) -> Optional[QuoteData]:
        try:
            ticker = yf.Ticker(symbol)
            fast_info = getattr(ticker, "fast_info", None)

            price: Optional[float] = None
            prev_close: Optional[float] = None
            open_price: Optional[float] = None
            high: Optional[float] = None
            low: Optional[float] = None
            volume: Optional[int] = None
            currency: str = "USD"

            if fast_info is not None:
                try:
                    price = getattr(fast_info, "last_price", None)
                    prev_close = getattr(fast_info, "previous_close", None)
                    open_price = getattr(fast_info, "open", None)
                    high = getattr(fast_info, "day_high", None)
                    low = getattr(fast_info, "day_low", None)
                    volume_raw = getattr(fast_info, "last_volume", None)
                    if volume_raw is not None and not math.isnan(volume_raw):
                        volume = int(volume_raw)
                    raw_currency = getattr(fast_info, "currency", None)
                    if raw_currency:
                        currency = str(raw_currency).upper()
                except Exception as e:
                    logger.debug("fast_info retrieval issue for %s: %s", symbol, e)

            # Fallback to history(period="5d") if price is missing or invalid
            if price is None or math.isnan(price) or price <= 0:
                hist = ticker.history(period="5d", interval="1d")
                if hist.empty or len(hist) == 0:
                    logger.warning("No price data returned from Yahoo Finance for %s", symbol)
                    return None

                latest_row = hist.iloc[-1]
                price = float(latest_row["Close"])
                if math.isnan(price) or price <= 0:
                    return None

                open_price = float(latest_row["Open"])
                high = float(latest_row["High"])
                low = float(latest_row["Low"])
                volume = int(latest_row["Volume"])

                if len(hist) > 1:
                    prev_close = float(hist.iloc[-2]["Close"])
                else:
                    prev_close = open_price

            if prev_close is None or math.isnan(prev_close) or prev_close <= 0:
                prev_close = price

            change = round(price - prev_close, 4)
            change_percent = round((change / prev_close) * 100, 4) if prev_close > 0 else 0.0

            # Default currency detection for Indian exchanges
            if symbol.endswith(".NS") or symbol.endswith(".BO"):
                currency = "INR"

            now_utc = datetime.now(timezone.utc)

            return QuoteData(
                symbol=symbol,
                price=round(price, 4),
                currency=currency,
                previous_close=round(prev_close, 4),
                change=change,
                change_percent=change_percent,
                open=round(open_price, 4) if open_price and not math.isnan(open_price) else None,
                high=round(high, 4) if high and not math.isnan(high) else None,
                low=round(low, 4) if low and not math.isnan(low) else None,
                volume=volume,
                timestamp=now_utc,
                retrieved_at=now_utc,
                provider=self.get_provider_name(),
                is_delayed=True,
                market_state="REGULAR",
                status="VALID",
            )
        except Exception as e:
            err_msg = str(e)
            if "Rate limited" in err_msg or "Too Many Requests" in err_msg:
                logger.warning("Yahoo Finance rate limit reached for %s: %s", symbol, err_msg)
            else:
                logger.error("Error fetching Yahoo Finance quote for %s: %s", symbol, err_msg)
            return None

    async def get_historical(
        self, symbol: str, period: str = "1mo", interval: str = "1d"
    ) -> Optional[HistoricalData]:
        clean_symbol = _sanitize_symbol(symbol)
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(
            None, self._sync_get_historical, clean_symbol, period, interval
        )

    def _sync_get_historical(
        self, symbol: str, period: str = "1mo", interval: str = "1d"
    ) -> Optional[HistoricalData]:
        try:
            ticker = yf.Ticker(symbol)
            # auto_adjust=False keeps Adj Close explicit when available
            df: pd.DataFrame = ticker.history(period=period, interval=interval, auto_adjust=False)

            if df.empty:
                logger.warning("No historical data returned for %s", symbol)
                return None

            currency = "INR" if symbol.endswith((".NS", ".BO")) else "USD"
            bars = []

            for index, row in df.iterrows():
                # Convert index to ISO date string
                if isinstance(index, pd.Timestamp):
                    date_str = index.strftime("%Y-%m-%d")
                else:
                    date_str = str(index)[:10]

                close_val = float(row.get("Close", 0.0))
                if math.isnan(close_val) or close_val <= 0:
                    continue

                adj_close = row.get("Adj Close")
                adj_close_val = (
                    float(adj_close) if adj_close is not None and not math.isnan(adj_close) else close_val
                )

                bars.append(
                    HistoricalBar(
                        date=date_str,
                        open=round(float(row.get("Open", close_val)), 4),
                        high=round(float(row.get("High", close_val)), 4),
                        low=round(float(row.get("Low", close_val)), 4),
                        close=round(close_val, 4),
                        volume=int(row.get("Volume", 0)),
                        adj_close=round(adj_close_val, 4),
                    )
                )

            return HistoricalData(
                symbol=symbol,
                currency=currency,
                provider=self.get_provider_name(),
                bars=bars,
                retrieved_at=datetime.now(timezone.utc),
            )
        except Exception as e:
            logger.error("Error fetching historical data for %s: %s", symbol, e)
            return None
