"""Rate limiting configuration using slowapi."""

import os

from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from starlette.requests import Request
from starlette.responses import JSONResponse

# Default: 100 requests per minute per IP
DEFAULT_LIMIT = os.getenv("RATE_LIMIT", "100/minute")

limiter = Limiter(key_func=get_remote_address, default_limits=[DEFAULT_LIMIT])


async def rate_limit_exceeded_handler(
    request: Request, exc: RateLimitExceeded
) -> JSONResponse:
    """Custom handler for rate limit exceeded errors."""
    return JSONResponse(
        status_code=429,
        content={
            "error": "Rate limit exceeded",
            "detail": str(exc.detail),
            "retry_after": exc.retry_after,
        },
    )
