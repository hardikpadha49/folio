"""
FolioPulse AI — Pydantic Schemas for CSV Import Operations
"""
import uuid
from typing import List, Optional
from pydantic import BaseModel


class CSVRowError(BaseModel):
    row: int
    column: str
    message: str
    raw_value: Optional[str] = None


class CSVHoldingRow(BaseModel):
    ticker: str
    name: Optional[str] = None
    quantity: float
    average_cost: float
    asset_class: str = "equity"
    sector: Optional[str] = None
    invested_value: float


class CSVPreviewResponse(BaseModel):
    total_rows: int
    valid_rows_count: int
    errors_count: int
    valid_rows: List[CSVHoldingRow]
    errors: List[CSVRowError]
    can_commit: bool


class CSVCommitResponse(BaseModel):
    portfolio_id: uuid.UUID
    imported_count: int
    message: str
