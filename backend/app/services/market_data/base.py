"""
FolioPulse AI — Market Data Common Interface and Domain Models

Standardizes quotes, historical bars, and provider operations across
Yahoo Finance, Alpha Vantage, and any future data source.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Any, List, Optional


@dataclass
class QuoteData:
    """Standardized market quote."""
    symbol: str
    price: float
    currency: str
    previous_close: float
    change: float
    change_percent: float
    open: Optional[float] = None
    high: Optional[float] = None
    low: Optional[float] = None
    volume: Optional[int] = None
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    retrieved_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    provider: str = "unknown"
    is_delayed: bool = True
    market_state: str = "UNKNOWN"  # REGULAR, CLOSED, PRE, POST, UNKNOWN
    status: str = "VALID"          # VALID, STALE, FALLBACK, UNRELIABLE

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["timestamp"] = self.timestamp.isoformat()
        data["retrieved_at"] = self.retrieved_at.isoformat()
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "QuoteData":
        d = dict(data)
        if isinstance(d.get("timestamp"), str):
            d["timestamp"] = datetime.fromisoformat(d["timestamp"])
        if isinstance(d.get("retrieved_at"), str):
            d["retrieved_at"] = datetime.fromisoformat(d["retrieved_at"])
        return cls(**d)


@dataclass
class HistoricalBar:
    """Single period OHLCV bar with optional adjusted close."""
    date: str
    open: float
    high: float
    low: float
    close: float
    volume: int
    adj_close: Optional[float] = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class HistoricalData:
    """Time-series data for a symbol."""
    symbol: str
    currency: str
    provider: str
    bars: List[HistoricalBar]
    retrieved_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict[str, Any]:
        return {
            "symbol": self.symbol,
            "currency": self.currency,
            "provider": self.provider,
            "bars": [b.to_dict() for b in self.bars],
            "retrieved_at": self.retrieved_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "HistoricalData":
        bars = [HistoricalBar(**b) for b in data.get("bars", [])]
        retrieved_at = (
            datetime.fromisoformat(data["retrieved_at"])
            if isinstance(data.get("retrieved_at"), str)
            else datetime.now(timezone.utc)
        )
        return cls(
            symbol=data["symbol"],
            currency=data.get("currency", "USD"),
            provider=data.get("provider", "unknown"),
            bars=bars,
            retrieved_at=retrieved_at,
        )


class BaseMarketDataProvider(ABC):
    """Abstract interface for all financial market data providers."""

    @abstractmethod
    def get_provider_name(self) -> str:
        """Unique identifier of the provider."""
        pass

    @abstractmethod
    async def is_available(self) -> bool:
        """Check provider operational status / credentials."""
        pass

    @abstractmethod
    async def get_quote(self, symbol: str) -> Optional[QuoteData]:
        """Fetch latest market quote for symbol."""
        pass

    @abstractmethod
    async def get_historical(
        self, symbol: str, period: str = "1mo", interval: str = "1d"
    ) -> Optional[HistoricalData]:
        """Fetch historical price series."""
        pass
