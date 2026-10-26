"""
FolioPulse AI — CSV Import Engine

Provides:
- CSV Template generation with sample financial instruments
- Strict validation: headers, data types, ranges, allowed asset classes
- Defense against CSV Formula Injection (CWE-1236)
- Row-level actionable error reporting
- Two-phase preview and atomic commit transaction
"""
import csv
import io
import re
import uuid
from typing import Optional, Set
from sqlalchemy.orm import Session

from app.core.exceptions import ValidationError, ConflictError, NotFoundError
from app.models.user import Portfolio, Holding
from app.schemas.csv_import import (
    CSVRowError,
    CSVHoldingRow,
    CSVPreviewResponse,
    CSVCommitResponse,
)

MAX_FILE_SIZE_BYTES = 5 * 1024 * 1024  # 5 MB
REQUIRED_COLUMNS = {"ticker", "quantity", "average_cost"}
ALLOWED_ASSET_CLASSES = {"equity", "debt", "etf", "commodity", "reit", "cash"}

# Regular expression to validate standard financial ticker symbols (e.g. RELIANCE.NS, ^NSEI, BRK.B, AAPL)
TICKER_REGEX = re.compile(r"^[\^A-Za-z0-9\.\-]{1,20}$")

SAMPLE_CSV_TEMPLATE = """# FolioPulse AI Holdings Import Template
# Supported asset_classes: equity, debt, etf, commodity, reit, cash
# For Indian equities use NSE symbol with .NS suffix (e.g. RELIANCE.NS, TCS.NS)
# For US equities use standard ticker (e.g. AAPL, MSFT)
ticker,name,quantity,average_cost,asset_class,sector
RELIANCE.NS,Reliance Industries Limited,10,2500.00,equity,Energy
TCS.NS,Tata Consultancy Services,15,3850.50,equity,Information Technology
INFY.NS,Infosys Limited,20,1750.25,equity,Information Technology
AAPL,Apple Inc.,5,185.50,equity,Technology
"""


def get_sample_csv_template() -> str:
    """Return standard template content."""
    return SAMPLE_CSV_TEMPLATE


def _sanitize_cell_text(val: Optional[str]) -> Optional[str]:
    """
    Sanitize text to prevent CSV/Spreadsheet Formula Injection.
    Strips leading dangerous characters (=, +, -, @, tab, cr).
    """
    if val is None:
        return None
    cleaned = val.strip()
    # Strip any leading formula characters
    while cleaned and cleaned[0] in ("=", "+", "-", "@", "\t", "\r"):
        cleaned = cleaned[1:].strip()
    return cleaned if cleaned else None


class CSVImportService:
    """Validates and processes CSV holdings imports."""

    @staticmethod
    def parse_and_validate(
        file_content: bytes, existing_tickers: Optional[Set[str]] = None
    ) -> CSVPreviewResponse:
        """Parse raw CSV bytes, validate all rows, and return preview with row-level errors."""
        if len(file_content) > MAX_FILE_SIZE_BYTES:
            raise ValidationError(f"File size exceeds maximum allowed limit of 5 MB.")

        try:
            # Decode UTF-8 (handles UTF-8 with BOM automatically via utf-8-sig)
            text_stream = file_content.decode("utf-8-sig")
        except UnicodeDecodeError:
            raise ValidationError("File encoding must be valid UTF-8.")

        # Ignore comment lines starting with '#'
        lines = [line for line in text_stream.splitlines() if line.strip() and not line.strip().startswith("#")]
        if not lines:
            raise ValidationError("CSV file is empty or contains only comments.")

        reader = csv.DictReader(lines)
        if not reader.fieldnames:
            raise ValidationError("Unable to read CSV headers.")

        # Normalize header keys: lowercase and stripped
        cleaned_headers = {h.strip().lower(): h for h in reader.fieldnames if h}
        missing = REQUIRED_COLUMNS - set(cleaned_headers.keys())
        if missing:
            raise ValidationError(f"Missing required CSV column(s): {', '.join(sorted(missing))}")

        errors: list[CSVRowError] = []
        valid_rows: list[CSVHoldingRow] = []
        seen_tickers: set[str] = set()
        portfolio_existing = existing_tickers or set()

        for idx, row in enumerate(reader, start=2):  # Line 2 is first data row
            # Extract fields with case-insensitive mapping
            raw_ticker = row.get(cleaned_headers.get("ticker", "ticker"))
            raw_qty = row.get(cleaned_headers.get("quantity", "quantity"))
            raw_cost = row.get(cleaned_headers.get("average_cost", "average_cost"))
            raw_name = row.get(cleaned_headers.get("name", "name"))
            raw_asset_class = row.get(cleaned_headers.get("asset_class", "asset_class"))
            raw_sector = row.get(cleaned_headers.get("sector", "sector"))

            # 1. Ticker validation
            if not raw_ticker or not raw_ticker.strip():
                errors.append(CSVRowError(row=idx, column="ticker", message="Ticker is required."))
                continue

            ticker = raw_ticker.strip().upper()
            if not TICKER_REGEX.match(ticker):
                errors.append(
                    CSVRowError(
                        row=idx,
                        column="ticker",
                        message=f"Invalid ticker format '{ticker}'. Use alphanumeric characters, dots, or hyphens.",
                        raw_value=raw_ticker,
                    )
                )
                continue

            if ticker in seen_tickers:
                errors.append(
                    CSVRowError(
                        row=idx,
                        column="ticker",
                        message=f"Duplicate ticker '{ticker}' in CSV file. Combine quantities into a single row.",
                        raw_value=ticker,
                    )
                )
                continue

            seen_tickers.add(ticker)

            if ticker in portfolio_existing:
                errors.append(
                    CSVRowError(
                        row=idx,
                        column="ticker",
                        message=f"Holding '{ticker}' already exists in this portfolio. Remove or edit holding directly.",
                        raw_value=ticker,
                    )
                )
                continue

            # 2. Quantity validation
            try:
                quantity = float(raw_qty) if raw_qty is not None else 0.0
                if quantity <= 0:
                    errors.append(
                        CSVRowError(
                            row=idx,
                            column="quantity",
                            message=f"Quantity must be a positive number. Got {raw_qty}.",
                            raw_value=str(raw_qty),
                        )
                    )
                    continue
            except (ValueError, TypeError):
                errors.append(
                    CSVRowError(
                        row=idx,
                        column="quantity",
                        message=f"Invalid quantity '{raw_qty}'. Must be a valid numeric value.",
                        raw_value=str(raw_qty),
                    )
                )
                continue

            # 3. Average Cost validation
            try:
                average_cost = float(raw_cost) if raw_cost is not None else 0.0
                if average_cost <= 0:
                    errors.append(
                        CSVRowError(
                            row=idx,
                            column="average_cost",
                            message=f"Average cost must be a positive number. Got {raw_cost}.",
                            raw_value=str(raw_cost),
                        )
                    )
                    continue
            except (ValueError, TypeError):
                errors.append(
                    CSVRowError(
                        row=idx,
                        column="average_cost",
                        message=f"Invalid average cost '{raw_cost}'. Must be a valid numeric value.",
                        raw_value=str(raw_cost),
                    )
                )
                continue

            # 4. Asset Class validation
            asset_class = "equity"
            if raw_asset_class and raw_asset_class.strip():
                clean_ac = raw_asset_class.strip().lower()
                if clean_ac not in ALLOWED_ASSET_CLASSES:
                    errors.append(
                        CSVRowError(
                            row=idx,
                            column="asset_class",
                            message=f"Invalid asset class '{clean_ac}'. Allowed: {', '.join(sorted(ALLOWED_ASSET_CLASSES))}.",
                            raw_value=raw_asset_class,
                        )
                    )
                    continue
                asset_class = clean_ac

            # 5. Sanitized optional strings
            name = _sanitize_cell_text(raw_name)
            sector = _sanitize_cell_text(raw_sector)

            seen_tickers.add(ticker)
            valid_rows.append(
                CSVHoldingRow(
                    ticker=ticker,
                    name=name,
                    quantity=quantity,
                    average_cost=average_cost,
                    asset_class=asset_class,
                    sector=sector,
                    invested_value=round(quantity * average_cost, 2),
                )
            )

        total_rows = len(valid_rows) + len(errors)
        return CSVPreviewResponse(
            total_rows=total_rows,
            valid_rows_count=len(valid_rows),
            errors_count=len(errors),
            valid_rows=valid_rows,
            errors=errors,
            can_commit=len(errors) == 0 and len(valid_rows) > 0,
        )

    @staticmethod
    def commit_import(
        portfolio_id: uuid.UUID,
        user_id: uuid.UUID,
        file_content: bytes,
        db: Session,
    ) -> CSVCommitResponse:
        """
        Atomically validate and insert all holdings in a single transaction.
        Rolls back completely if any row validation fails or conflict arises.
        """
        portfolio = db.get(Portfolio, portfolio_id)
        if not portfolio or not portfolio.is_active or portfolio.user_id != user_id:
            raise NotFoundError("Portfolio")

        # Fetch existing tickers for this portfolio
        existing_holdings = (
            db.query(Holding.ticker).filter(Holding.portfolio_id == portfolio_id).all()
        )
        existing_tickers = {h[0] for h in existing_holdings}

        preview = CSVImportService.parse_and_validate(file_content, existing_tickers=existing_tickers)
        if not preview.can_commit:
            raise ValidationError(
                f"Cannot commit CSV import: {preview.errors_count} error(s) found. Fix rows before importing."
            )

        # Atomic bulk creation inside session transaction
        try:
            for row in preview.valid_rows:
                holding = Holding(
                    portfolio_id=portfolio_id,
                    ticker=row.ticker,
                    name=row.name,
                    quantity=row.quantity,
                    average_cost=row.average_cost,
                    asset_class=row.asset_class,
                    sector=row.sector,
                )
                db.add(holding)

            db.commit()
            return CSVCommitResponse(
                portfolio_id=portfolio_id,
                imported_count=len(preview.valid_rows),
                message=f"Successfully imported {len(preview.valid_rows)} holding(s).",
            )
        except Exception as e:
            db.rollback()
            logger.error("CSV atomic commit failed: %s", e)
            raise ValidationError(f"Failed to commit holdings: {str(e)}")
