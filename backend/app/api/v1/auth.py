"""
FolioPulse AI — Auth API Routes

Endpoints:
  POST /api/v1/auth/register   — Create new user
  POST /api/v1/auth/login      — Obtain JWT pair
  POST /api/v1/auth/refresh    — Exchange refresh token for new access token
  POST /api/v1/auth/logout     — Revoke refresh token
  GET  /api/v1/auth/me         — Get current user profile
"""
import uuid
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.dependencies import CurrentUser, DBSession
from app.core.exceptions import ConflictError, AuthenticationError
from app.core.security import (
    hash_password,
    verify_password,
    create_access_token,
    generate_refresh_token,
    hash_refresh_token,
    refresh_token_expiry,
    decode_access_token,
)
from app.config import get_settings
from app.models.user import User, RefreshToken
from app.schemas.auth import (
    RegisterRequest,
    LoginRequest,
    RefreshRequest,
    TokenResponse,
    AccessTokenResponse,
    UserResponse,
)

router = APIRouter(prefix="/auth", tags=["Authentication"])
settings = get_settings()


def _build_token_response(user: User, db: Session) -> TokenResponse:
    """Create access + refresh tokens, persist the refresh token hash."""
    access_token = create_access_token(str(user.id))
    raw_refresh = generate_refresh_token()
    hashed_refresh = hash_refresh_token(raw_refresh)

    db_token = RefreshToken(
        user_id=user.id,
        token_hash=hashed_refresh,
        expires_at=refresh_token_expiry(),
    )
    db.add(db_token)
    db.commit()

    return TokenResponse(
        access_token=access_token,
        refresh_token=raw_refresh,
        expires_in=settings.access_token_expire_minutes * 60,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Register
# ─────────────────────────────────────────────────────────────────────────────
@router.post(
    "/register",
    response_model=TokenResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user",
)
def register(payload: RegisterRequest, db: DBSession):
    existing = db.query(User).filter(User.email == payload.email.lower()).first()
    if existing:
        raise ConflictError("An account with this email already exists")

    user = User(
        email=payload.email.lower(),
        full_name=payload.full_name.strip(),
        hashed_password=hash_password(payload.password),
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    return _build_token_response(user, db)


# ─────────────────────────────────────────────────────────────────────────────
# Login
# ─────────────────────────────────────────────────────────────────────────────
@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Login and obtain JWT tokens",
)
def login(payload: LoginRequest, db: DBSession):
    user = db.query(User).filter(User.email == payload.email.lower()).first()
    if not user or not verify_password(payload.password, user.hashed_password):
        # Always return the same error to prevent user enumeration
        raise AuthenticationError("Invalid email or password")

    if not user.is_active:
        raise AuthenticationError("Account is disabled")

    return _build_token_response(user, db)


# ─────────────────────────────────────────────────────────────────────────────
# Refresh
# ─────────────────────────────────────────────────────────────────────────────
@router.post(
    "/refresh",
    response_model=AccessTokenResponse,
    summary="Exchange a valid refresh token for a new access token",
)
def refresh_token(payload: RefreshRequest, db: DBSession):
    hashed = hash_refresh_token(payload.refresh_token)
    db_token = (
        db.query(RefreshToken)
        .filter(
            RefreshToken.token_hash == hashed,
            RefreshToken.revoked == False,  # noqa: E712
        )
        .first()
    )

    if not db_token:
        raise AuthenticationError("Invalid or expired refresh token")

    # Handle both timezone-aware (PostgreSQL) and naive (SQLite in tests) datetimes
    expires_at = db_token.expires_at
    now = datetime.now(timezone.utc)
    if expires_at.tzinfo is None:
        # SQLite stores naive datetimes; compare as UTC naive
        now = datetime.utcnow()
    if expires_at < now:
        db_token.revoked = True
        db.commit()
        raise AuthenticationError("Refresh token has expired")

    user = db.get(User, db_token.user_id)
    if not user or not user.is_active:
        raise AuthenticationError("User account not found or disabled")

    access_token = create_access_token(str(user.id))
    return AccessTokenResponse(
        access_token=access_token,
        expires_in=settings.access_token_expire_minutes * 60,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Logout
# ─────────────────────────────────────────────────────────────────────────────
@router.post(
    "/logout",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Revoke the current refresh token",
)
def logout(payload: RefreshRequest, db: DBSession):
    hashed = hash_refresh_token(payload.refresh_token)
    db_token = (
        db.query(RefreshToken)
        .filter(RefreshToken.token_hash == hashed)
        .first()
    )
    if db_token:
        db_token.revoked = True
        db.commit()
    # Always return 204 — don't reveal whether token existed


# ─────────────────────────────────────────────────────────────────────────────
# Me
# ─────────────────────────────────────────────────────────────────────────────
@router.get(
    "/me",
    response_model=UserResponse,
    summary="Get current authenticated user profile",
)
def me(current_user: CurrentUser):
    return current_user
