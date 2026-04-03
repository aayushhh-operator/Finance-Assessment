"""Middleware for attaching rate limit headers to responses."""

from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.rate_limiting.storage import RateLimitResult


class RateLimitHeadersMiddleware(BaseHTTPMiddleware):
    """Add rate limit headers for requests that were evaluated by the limiter."""

    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)
        result: RateLimitResult | None = getattr(request.state, "rate_limit_result", None)
        if result is None:
            return response

        response.headers["X-RateLimit-Limit"] = str(result.limit)
        response.headers["X-RateLimit-Remaining"] = str(result.remaining)
        response.headers["X-RateLimit-Reset"] = str(result.reset_at)
        if not result.allowed:
            response.headers["Retry-After"] = str(result.retry_after)
        return response
