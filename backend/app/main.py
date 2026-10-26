"""
FolioPulse AI — FastAPI Application Factory
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware

from app.config import get_settings
from app.core.exceptions import FolioPulseException, foliopulse_exception_handler
from app.api.v1 import auth, portfolios, holdings

settings = get_settings()


def create_app() -> FastAPI:
    app = FastAPI(
        title="FolioPulse AI",
        description="AI-powered investment portfolio analysis platform",
        version="0.1.0",
        docs_url="/docs" if not settings.is_production else None,
        redoc_url="/redoc" if not settings.is_production else None,
    )

    # ── Middleware ────────────────────────────────────────────────────────────
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[settings.frontend_url],
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type"],
    )

    # ── Exception handlers ───────────────────────────────────────────────────
    app.add_exception_handler(FolioPulseException, foliopulse_exception_handler)

    # ── Routers ──────────────────────────────────────────────────────────────
    API_PREFIX = "/api/v1"
    app.include_router(auth.router, prefix=API_PREFIX)
    app.include_router(portfolios.router, prefix=API_PREFIX)
    app.include_router(holdings.router, prefix=API_PREFIX)

    # ── Health check ─────────────────────────────────────────────────────────
    @app.get("/health", tags=["System"])
    def health_check():
        return {
            "status": "ok",
            "version": "0.1.0",
            "environment": settings.app_env,
        }

    return app


app = create_app()
