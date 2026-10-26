"""
FolioPulse AI — Pydantic Schemas for Portfolio and Holding endpoints
"""
import uuid
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, field_validator


# ─────────────────────────────────────────────────────────────────────────────
# Portfolio schemas
# ─────────────────────────────────────────────────────────────────────────────
class PortfolioCreate(BaseModel):
    name: str
    description: Optional[str] = None
    currency: str = "INR"

    @field_validator("name")
    @classmethod
    def name_not_empty(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Portfolio name cannot be empty")
        if len(v) > 255:
            raise ValueError("Portfolio name too long")
        return v

    @field_validator("currency")
    @classmethod
    def valid_currency(cls, v: str) -> str:
        allowed = {"INR", "USD", "EUR", "GBP"}
        v = v.upper()
        if v not in allowed:
            raise ValueError(f"Currency must be one of {allowed}")
        return v


class PortfolioUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None


class PortfolioResponse(BaseModel):
    id: uuid.UUID
    name: str
    description: Optional[str]
    currency: str
    is_active: bool
    created_at: datetime
    updated_at: datetime
    holding_count: int = 0

    model_config = {"from_attributes": True}


# ─────────────────────────────────────────────────────────────────────────────
# Holding schemas
# ─────────────────────────────────────────────────────────────────────────────
VALID_ASSET_CLASSES = {"equity", "debt", "etf", "commodity", "reit", "cash"}


class HoldingCreate(BaseModel):
    ticker: str
    name: Optional[str] = None
    quantity: float
    average_cost: float
    asset_class: str = "equity"
    sector: Optional[str] = None

    @field_validator("ticker")
    @classmethod
    def ticker_not_empty(cls, v: str) -> str:
        v = v.strip().upper()
        if not v:
            raise ValueError("Ticker cannot be empty")
        if len(v) > 20:
            raise ValueError("Ticker too long")
        return v

    @field_validator("quantity")
    @classmethod
    def quantity_positive(cls, v: float) -> float:
        if v <= 0:
            raise ValueError("Quantity must be positive")
        return v

    @field_validator("average_cost")
    @classmethod
    def cost_positive(cls, v: float) -> float:
        if v <= 0:
            raise ValueError("Average cost must be positive")
        return v

    @field_validator("asset_class")
    @classmethod
    def valid_asset_class(cls, v: str) -> str:
        v = v.lower()
        if v not in VALID_ASSET_CLASSES:
            raise ValueError(f"asset_class must be one of {VALID_ASSET_CLASSES}")
        return v


class HoldingUpdate(BaseModel):
    quantity: Optional[float] = None
    average_cost: Optional[float] = None
    name: Optional[str] = None
    sector: Optional[str] = None


class HoldingResponse(BaseModel):
    id: uuid.UUID
    portfolio_id: uuid.UUID
    ticker: str
    name: Optional[str]
    quantity: float
    average_cost: float
    asset_class: str
    sector: Optional[str]
    invested_value: float
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}

    @classmethod
    def from_orm_with_computed(cls, holding: object) -> "HoldingResponse":
        return cls(
            id=holding.id,
            portfolio_id=holding.portfolio_id,
            ticker=holding.ticker,
            name=holding.name,
            quantity=holding.quantity,
            average_cost=holding.average_cost,
            asset_class=holding.asset_class,
            sector=holding.sector,
            invested_value=round(holding.quantity * holding.average_cost, 2),
            created_at=holding.created_at,
            updated_at=holding.updated_at,
        )
