"""
FolioPulse AI — Portfolios API Routes

All routes are protected. Every query filters on current_user.id —
user isolation is enforced at the query level, not just by convention.

Endpoints:
  GET    /api/v1/portfolios                   — List current user's portfolios
  POST   /api/v1/portfolios                   — Create a new portfolio
  GET    /api/v1/portfolios/csv/template      — Download holdings CSV template
  GET    /api/v1/portfolios/{id}              — Get a specific portfolio
  PATCH  /api/v1/portfolios/{id}              — Update portfolio name/description
  DELETE /api/v1/portfolios/{id}              — Soft-delete (set is_active=False)
  GET    /api/v1/portfolios/{id}/valuation    — Get market valuation with live quotes
  POST   /api/v1/portfolios/{id}/csv/preview  — Validate CSV and preview rows
  POST   /api/v1/portfolios/{id}/csv/commit   — Atomically import validated holdings
"""
import uuid
from typing import List

from fastapi import APIRouter, File, Query, Response, UploadFile, status
from fastapi.responses import PlainTextResponse

from app.core.dependencies import CurrentUser, DBSession
from app.core.exceptions import NotFoundError, ConflictError
from app.models.user import Portfolio, Holding
from app.schemas.portfolio import (
    PortfolioCreate,
    PortfolioUpdate,
    PortfolioResponse,
)
from app.schemas.valuation import PortfolioValuationResponse
from app.schemas.csv_import import CSVPreviewResponse, CSVCommitResponse
from app.services.valuation import get_valuation_service
from app.services.csv_import import CSVImportService, get_sample_csv_template

router = APIRouter(prefix="/portfolios", tags=["Portfolios"])


def _get_portfolio_or_raise(
    portfolio_id: uuid.UUID, user_id: uuid.UUID, db
) -> Portfolio:
    """Fetch a portfolio — raises 404 to avoid disclosing existence across users."""
    portfolio = db.get(Portfolio, portfolio_id)
    if portfolio is None or not portfolio.is_active or portfolio.user_id != user_id:
        raise NotFoundError("Portfolio")
    return portfolio


@router.get("", response_model=List[PortfolioResponse], summary="List my portfolios")
def list_portfolios(current_user: CurrentUser, db: DBSession):
    portfolios = (
        db.query(Portfolio)
        .filter(Portfolio.user_id == current_user.id, Portfolio.is_active == True)  # noqa: E712
        .order_by(Portfolio.created_at.desc())
        .all()
    )
    result = []
    for p in portfolios:
        d = PortfolioResponse.model_validate(p)
        d.holding_count = len([h for h in p.holdings])
        result.append(d)
    return result


@router.post(
    "",
    response_model=PortfolioResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new portfolio",
)
def create_portfolio(
    payload: PortfolioCreate, current_user: CurrentUser, db: DBSession
):
    existing = (
        db.query(Portfolio)
        .filter(
            Portfolio.user_id == current_user.id,
            Portfolio.name == payload.name.strip(),
            Portfolio.is_active == True,  # noqa: E712
        )
        .first()
    )
    if existing:
        raise ConflictError(f"You already have a portfolio named '{payload.name}'")

    portfolio = Portfolio(
        user_id=current_user.id,
        name=payload.name.strip(),
        description=payload.description,
        currency=payload.currency,
    )
    db.add(portfolio)
    db.commit()
    db.refresh(portfolio)

    response = PortfolioResponse.model_validate(portfolio)
    response.holding_count = 0
    return response


@router.get(
    "/csv/template",
    response_class=PlainTextResponse,
    summary="Download sample CSV template for holdings import",
)
def download_csv_template():
    content = get_sample_csv_template()
    return PlainTextResponse(
        content=content,
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="holdings_template.csv"'},
    )


@router.get(
    "/{portfolio_id}",
    response_model=PortfolioResponse,
    summary="Get a specific portfolio",
)
def get_portfolio(
    portfolio_id: uuid.UUID, current_user: CurrentUser, db: DBSession
):
    portfolio = _get_portfolio_or_raise(portfolio_id, current_user.id, db)
    response = PortfolioResponse.model_validate(portfolio)
    response.holding_count = len(portfolio.holdings)
    return response


@router.patch(
    "/{portfolio_id}",
    response_model=PortfolioResponse,
    summary="Update portfolio name or description",
)
def update_portfolio(
    portfolio_id: uuid.UUID,
    payload: PortfolioUpdate,
    current_user: CurrentUser,
    db: DBSession,
):
    portfolio = _get_portfolio_or_raise(portfolio_id, current_user.id, db)

    if payload.name is not None:
        portfolio.name = payload.name.strip()
    if payload.description is not None:
        portfolio.description = payload.description

    db.commit()
    db.refresh(portfolio)

    response = PortfolioResponse.model_validate(portfolio)
    response.holding_count = len(portfolio.holdings)
    return response


@router.delete(
    "/{portfolio_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a portfolio (soft delete)",
)
def delete_portfolio(
    portfolio_id: uuid.UUID, current_user: CurrentUser, db: DBSession
):
    portfolio = _get_portfolio_or_raise(portfolio_id, current_user.id, db)
    portfolio.is_active = False
    db.commit()


# ─────────────────────────────────────────────────────────────────────────────
# Valuation
# ─────────────────────────────────────────────────────────────────────────────
@router.get(
    "/{portfolio_id}/valuation",
    response_model=PortfolioValuationResponse,
    summary="Calculate real-time portfolio market valuation with current quotes",
)
async def get_portfolio_valuation(
    portfolio_id: uuid.UUID,
    current_user: CurrentUser,
    db: DBSession,
    refresh: bool = Query(False, description="Force fresh market quotes"),
):
    portfolio = _get_portfolio_or_raise(portfolio_id, current_user.id, db)
    val_service = get_valuation_service()
    return await val_service.value_portfolio(portfolio, force_refresh=refresh)


# ─────────────────────────────────────────────────────────────────────────────
# CSV Import Preview & Commit
# ─────────────────────────────────────────────────────────────────────────────
@router.post(
    "/{portfolio_id}/csv/preview",
    response_model=CSVPreviewResponse,
    summary="Validate CSV file and return preview without committing to database",
)
async def preview_csv_import(
    portfolio_id: uuid.UUID,
    current_user: CurrentUser,
    db: DBSession,
    file: UploadFile = File(...),
):
    _get_portfolio_or_raise(portfolio_id, current_user.id, db)

    existing_holdings = (
        db.query(Holding.ticker).filter(Holding.portfolio_id == portfolio_id).all()
    )
    existing_tickers = {h[0] for h in existing_holdings}

    content = await file.read()
    return CSVImportService.parse_and_validate(content, existing_tickers=existing_tickers)


@router.post(
    "/{portfolio_id}/csv/commit",
    response_model=CSVCommitResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Atomically commit validated CSV holdings to portfolio",
)
async def commit_csv_import(
    portfolio_id: uuid.UUID,
    current_user: CurrentUser,
    db: DBSession,
    file: UploadFile = File(...),
):
    content = await file.read()
    return CSVImportService.commit_import(
        portfolio_id=portfolio_id,
        user_id=current_user.id,
        file_content=content,
        db=db,
    )
