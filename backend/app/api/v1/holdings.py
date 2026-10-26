"""
FolioPulse AI — Holdings API Routes

Endpoints:
  GET    /api/v1/portfolios/{portfolio_id}/holdings        — List holdings
  POST   /api/v1/portfolios/{portfolio_id}/holdings        — Add a holding
  PATCH  /api/v1/portfolios/{portfolio_id}/holdings/{id}   — Update a holding
  DELETE /api/v1/portfolios/{portfolio_id}/holdings/{id}   — Remove a holding
"""
import uuid
from typing import List

from fastapi import APIRouter, status

from app.core.dependencies import CurrentUser, DBSession
from app.core.exceptions import NotFoundError, ConflictError
from app.models.user import Portfolio, Holding
from app.schemas.portfolio import HoldingCreate, HoldingUpdate, HoldingResponse

router = APIRouter(
    prefix="/portfolios/{portfolio_id}/holdings", tags=["Holdings"]
)


def _get_portfolio_owned_by(portfolio_id: uuid.UUID, user_id: uuid.UUID, db):
    portfolio = db.get(Portfolio, portfolio_id)
    if not portfolio or not portfolio.is_active or portfolio.user_id != user_id:
        raise NotFoundError("Portfolio")
    return portfolio


def _get_holding(holding_id: uuid.UUID, portfolio_id: uuid.UUID, db) -> Holding:
    holding = db.get(Holding, holding_id)
    if not holding or holding.portfolio_id != portfolio_id:
        raise NotFoundError("Holding")
    return holding


@router.get("", response_model=List[HoldingResponse], summary="List holdings in portfolio")
def list_holdings(
    portfolio_id: uuid.UUID, current_user: CurrentUser, db: DBSession
):
    _get_portfolio_owned_by(portfolio_id, current_user.id, db)
    holdings = (
        db.query(Holding)
        .filter(Holding.portfolio_id == portfolio_id)
        .order_by(Holding.ticker)
        .all()
    )
    return [HoldingResponse.from_orm_with_computed(h) for h in holdings]


@router.post(
    "",
    response_model=HoldingResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add a holding to the portfolio",
)
def add_holding(
    portfolio_id: uuid.UUID,
    payload: HoldingCreate,
    current_user: CurrentUser,
    db: DBSession,
):
    _get_portfolio_owned_by(portfolio_id, current_user.id, db)

    existing = (
        db.query(Holding)
        .filter(
            Holding.portfolio_id == portfolio_id,
            Holding.ticker == payload.ticker,
        )
        .first()
    )
    if existing:
        raise ConflictError(
            f"Holding '{payload.ticker}' already exists in this portfolio. "
            "Use PATCH to update it."
        )

    holding = Holding(
        portfolio_id=portfolio_id,
        ticker=payload.ticker,
        name=payload.name,
        quantity=payload.quantity,
        average_cost=payload.average_cost,
        asset_class=payload.asset_class,
        sector=payload.sector,
    )
    db.add(holding)
    db.commit()
    db.refresh(holding)
    return HoldingResponse.from_orm_with_computed(holding)


@router.patch(
    "/{holding_id}",
    response_model=HoldingResponse,
    summary="Update a holding's quantity or cost",
)
def update_holding(
    portfolio_id: uuid.UUID,
    holding_id: uuid.UUID,
    payload: HoldingUpdate,
    current_user: CurrentUser,
    db: DBSession,
):
    _get_portfolio_owned_by(portfolio_id, current_user.id, db)
    holding = _get_holding(holding_id, portfolio_id, db)

    if payload.quantity is not None:
        holding.quantity = payload.quantity
    if payload.average_cost is not None:
        holding.average_cost = payload.average_cost
    if payload.name is not None:
        holding.name = payload.name
    if payload.sector is not None:
        holding.sector = payload.sector

    db.commit()
    db.refresh(holding)
    return HoldingResponse.from_orm_with_computed(holding)


@router.delete(
    "/{holding_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remove a holding from the portfolio",
)
def delete_holding(
    portfolio_id: uuid.UUID,
    holding_id: uuid.UUID,
    current_user: CurrentUser,
    db: DBSession,
):
    _get_portfolio_owned_by(portfolio_id, current_user.id, db)
    holding = _get_holding(holding_id, portfolio_id, db)
    db.delete(holding)
    db.commit()
