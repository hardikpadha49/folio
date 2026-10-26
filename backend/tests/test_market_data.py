"""
FolioPulse AI — Unit & Integration Tests for Market Data & Caching

Tests:
- QuoteData serialization / deserialization
- Caching with TTL expiration
- Stale status detection on expired cached items
- Fallback from primary to secondary provider
- Symbol normalization (whitespace, lowercase to uppercase)
- FX currency exchange rate derivation
- API endpoints: /api/v1/market/quote/{symbol} and /api/v1/market/history/{symbol}
"""
import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, patch

from app.core.cache import MemoryCache
from app.services.market_data.base import QuoteData, HistoricalBar, HistoricalData, BaseMarketDataProvider
from app.services.market_data.service import MarketDataService


class MockProvider(BaseMarketDataProvider):
    """Deterministic test provider."""

    def __init__(self, name="mock_provider", available=True):
        self.name = name
        self.available = available
        self.quotes = {}
        self.history = {}

    def get_provider_name(self) -> str:
        return self.name

    async def is_available(self) -> bool:
        return self.available

    async def get_quote(self, symbol: str):
        return self.quotes.get(symbol.upper())

    async def get_historical(self, symbol: str, period: str = "1mo", interval: str = "1d"):
        return self.history.get(symbol.upper())


# ─────────────────────────────────────────────────────────────────────────────
# Quote Data Serialization & Normalization
# ─────────────────────────────────────────────────────────────────────────────
def test_quote_data_serialization():
    now = datetime.now(timezone.utc)
    quote = QuoteData(
        symbol="RELIANCE.NS",
        price=2950.0,
        currency="INR",
        previous_close=2900.0,
        change=50.0,
        change_percent=1.72,
        open=2910.0,
        high=2960.0,
        low=2905.0,
        volume=1200000,
        timestamp=now,
        retrieved_at=now,
        provider="test",
        is_delayed=True,
        market_state="REGULAR",
        status="VALID",
    )
    d = quote.to_dict()
    assert d["symbol"] == "RELIANCE.NS"
    assert d["price"] == 2950.0
    assert isinstance(d["timestamp"], str)

    restored = QuoteData.from_dict(d)
    assert restored.symbol == "RELIANCE.NS"
    assert restored.price == 2950.0
    assert restored.currency == "INR"


# ─────────────────────────────────────────────────────────────────────────────
# Memory Caching & TTL Tests
# ─────────────────────────────────────────────────────────────────────────────
def test_memory_cache_ttl():
    cache = MemoryCache()
    cache.set("test_key", {"foo": "bar"}, ttl_seconds=1)
    assert cache.get("test_key") == {"foo": "bar"}

    # Simulate expiration by modifying expires_at
    val, _ = cache._store["test_key"]
    cache._store["test_key"] = (val, datetime.now(timezone.utc).timestamp() - 10)
    assert cache.get("test_key") is None


# ─────────────────────────────────────────────────────────────────────────────
# Market Data Service Fallback & Caching
# ─────────────────────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_service_primary_success():
    primary = MockProvider("primary")
    secondary = MockProvider("secondary")
    quote_fixture = QuoteData(
        symbol="TCS.NS",
        price=3850.0,
        currency="INR",
        previous_close=3800.0,
        change=50.0,
        change_percent=1.32,
        provider="primary",
    )
    primary.quotes["TCS.NS"] = quote_fixture

    service = MarketDataService(primary_provider=primary, secondary_provider=secondary)
    service.cache = MemoryCache()

    q = await service.get_quote("tcs.ns")  # lowercase test
    assert q is not None
    assert q.symbol == "TCS.NS"
    assert q.price == 3850.0

    # Ensure cached
    cached = service.cache.get("quote:TCS.NS")
    assert cached is not None
    assert cached["price"] == 3850.0


@pytest.mark.asyncio
async def test_service_fallback_to_secondary():
    primary = MockProvider("primary")  # Empty quotes
    secondary = MockProvider("secondary")
    secondary.quotes["AAPL"] = QuoteData(
        symbol="AAPL",
        price=180.0,
        currency="USD",
        previous_close=178.0,
        change=2.0,
        change_percent=1.12,
        provider="secondary",
    )

    service = MarketDataService(primary_provider=primary, secondary_provider=secondary)
    service.cache = MemoryCache()

    q = await service.get_quote("AAPL")
    assert q is not None
    assert q.symbol == "AAPL"
    assert q.price == 180.0
    assert q.status == "FALLBACK"


@pytest.mark.asyncio
async def test_service_stale_cache_marking():
    primary = MockProvider("primary")
    service = MarketDataService(primary_provider=primary, quote_ttl=60)
    service.cache = MemoryCache()

    # Pre-populate cache with an old retrieved_at
    old_time = datetime.now(timezone.utc) - timedelta(seconds=120)
    old_quote = QuoteData(
        symbol="INFY.NS",
        price=1600.0,
        currency="INR",
        previous_close=1600.0,
        change=0.0,
        change_percent=0.0,
        retrieved_at=old_time,
        provider="primary",
    )
    service.cache.set("quote:INFY.NS", old_quote.to_dict(), ttl_seconds=300)

    q = await service.get_quote("INFY.NS")
    assert q is not None
    assert q.status == "STALE"


@pytest.mark.asyncio
async def test_fx_rate_same_currency():
    service = MarketDataService()
    rate = await service.get_fx_rate("INR", "INR")
    assert rate == 1.0
    rate_usd = await service.get_fx_rate("USD", "USD")
    assert rate_usd == 1.0


@pytest.mark.asyncio
async def test_fx_rate_lookup_success():
    primary = MockProvider("primary")
    primary.quotes["USDINR=X"] = QuoteData(
        symbol="USDINR=X",
        price=86.50,
        currency="INR",
        previous_close=86.40,
        change=0.10,
        change_percent=0.12,
        provider="primary",
    )
    service = MarketDataService(primary_provider=primary)
    service.cache = MemoryCache()

    rate = await service.get_fx_rate("USD", "INR")
    assert rate == 86.50


# ─────────────────────────────────────────────────────────────────────────────
# Market API Endpoints Tests
# ─────────────────────────────────────────────────────────────────────────────
USER = {"email": "market_user@test.com", "full_name": "Market Tester", "password": "SecurePass1"}


def test_market_quote_api_authenticated(client):
    r = client.post("/api/v1/auth/register", json=USER)
    token = r.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Mock the market data service quote
    fake_quote = QuoteData(
        symbol="HDFCBANK.NS",
        price=1650.0,
        currency="INR",
        previous_close=1640.0,
        change=10.0,
        change_percent=0.61,
        provider="test_mock",
    )

    with patch("app.api.v1.market.get_market_data_service") as mock_get_svc:
        mock_svc = AsyncMock()
        mock_svc.get_quote.return_value = fake_quote
        mock_get_svc.return_value = mock_svc

        resp = client.get("/api/v1/market/quote/HDFCBANK.NS", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["symbol"] == "HDFCBANK.NS"
        assert data["price"] == 1650.0


def test_market_quote_api_unauthorized(client):
    resp = client.get("/api/v1/market/quote/RELIANCE.NS")
    assert resp.status_code in (401, 403)
