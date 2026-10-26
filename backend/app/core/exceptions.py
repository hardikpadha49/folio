"""
FolioPulse AI — Custom Exceptions and HTTP Exception Handlers
"""
from fastapi import Request
from fastapi.responses import JSONResponse


class FolioPulseException(Exception):
    """Base for all application exceptions."""
    def __init__(self, message: str, status_code: int = 400):
        self.message = message
        self.status_code = status_code
        super().__init__(message)


class AuthenticationError(FolioPulseException):
    def __init__(self, message: str = "Authentication failed"):
        super().__init__(message, status_code=401)


class AuthorizationError(FolioPulseException):
    def __init__(self, message: str = "Access denied"):
        super().__init__(message, status_code=403)


class NotFoundError(FolioPulseException):
    def __init__(self, resource: str = "Resource"):
        super().__init__(f"{resource} not found", status_code=404)


class ConflictError(FolioPulseException):
    def __init__(self, message: str = "Resource already exists"):
        super().__init__(message, status_code=409)


class ValidationError(FolioPulseException):
    def __init__(self, message: str):
        super().__init__(message, status_code=422)


# ─────────────────────────────────────────────────────────────────────────────
# Global exception handlers (registered in main.py)
# ─────────────────────────────────────────────────────────────────────────────
async def foliopulse_exception_handler(
    request: Request, exc: FolioPulseException
) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.message, "type": type(exc).__name__},
    )
