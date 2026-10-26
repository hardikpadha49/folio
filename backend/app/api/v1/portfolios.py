"""
FolioPulse AI — Portfolios API Routes

All routes are protected. Every query filters on current_user.id —
user isolation is enforced at the query level, not just by convention.

Endpoints:
  GET    /api/v1/portfolios          — List current user's portfolios
  POST   /api/v1/portfolios          — Create a new portfolio
  GET    /api/v1/portfolios/{id}     — Get a specific portfolio
  PATCH  /api/v1/portfolios/{id}     — Update portfolio name/description
  DELETE /api/v1/portfolios/{id}     — Soft-delete (set is_active=False)
"""
import uuid
from typing import List

from fastapi import APIRouter, HTTPException, status

from app.core.dependencies import CurrentUser, DBSession
from app.core.exceptions import NotFoundError, AuthorizationError, ConflictError
from app.models.user import Portfolio
from app.schemas.portfolio import (
    PortfolioCreate,
    PortfolioUpdate,
    PortfolioResponse,
)

router = APIRouter(prefix="/portfolios", tags=["Portfolios"])


def _get_portfolio_or_raise(
    portfolio_id: uuid.UUID, user_id: uuid.UUID, db
) -> Portfolio:
    """Fetch a portfolio — raises 404 or 403 as appropriate."""
    portfolio = db.get(Portfolio, portfolio_id)
    if portfolio is None or not portfolio.is_active:
        raise NotFoundError("Portfolio")
    if portfolio.user_id != user_id:
        # Return 404 rather than 403 to avoid disclosing existence to other users
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
    # Check uniqueness for this user
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
