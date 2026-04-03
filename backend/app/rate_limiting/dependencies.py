"""FastAPI dependency helpers for applying rate limits."""

from __future__ import annotations

from collections.abc import Callable
from typing import Literal

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.rate_limiting.rules import RateLimitRule
from app.rate_limiting.storage import InMemoryRateLimitStorage, RateLimitResult
from app.services.auth_service import decode_token
from app.services.user_service import get_user_by_email

KeyStrategy = Literal["ip", "user", "user+ip"]

rate_limit_storage = InMemoryRateLimitStorage()


def get_rate_limit_storage() -> InMemoryRateLimitStorage:
    """Return the shared rate limit storage instance."""

    return rate_limit_storage


def get_client_ip(request: Request) -> str:
    """Extract the client IP with proxy support."""

    forwarded_for = request.headers.get("x-forwarded-for")
    if forwarded_for:
        first_ip = forwarded_for.split(",")[0].strip()
        if first_ip:
            return first_ip

    if request.client and request.client.host:
        return request.client.host

    return "unknown"


def get_bearer_token(request: Request) -> str | None:
    """Read the bearer token without raising when it is missing or malformed."""

    authorization = request.headers.get("authorization")
    if not authorization:
        return None

    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        return None
    return token.strip()


def resolve_user_for_rate_limit(request: Request, db: Session) -> User | None:
    """Best-effort user lookup for user-based limits.

    The limiter should not be the component that rejects authentication. If the
    token is missing or invalid we simply fall back to IP-based keys and let the
    route's normal auth dependency return the appropriate 401/403 response.
    """

    cached_user = getattr(request.state, "current_user", None)
    if cached_user is not None:
        return cached_user

    token = get_bearer_token(request)
    if not token:
        return None

    try:
        payload = decode_token(token)
    except ValueError:
        return None

    email = payload.get("sub")
    if not email:
        return None
    return get_user_by_email(db, email)


def build_rate_limit_key(
    request: Request,
    rule: RateLimitRule,
    key_strategy: KeyStrategy,
    db: Session,
) -> str:
    """Build a stable storage key for the selected strategy."""

    client_ip = get_client_ip(request)
    if key_strategy == "ip":
        return f"rate:{rule.name}:ip:{client_ip}"

    user = resolve_user_for_rate_limit(request, db)
    if user is None:
        return f"rate:{rule.name}:ip:{client_ip}"

    if key_strategy == "user":
        return f"rate:{rule.name}:user:{user.id}"

    return f"rate:{rule.name}:user:{user.id}:ip:{client_ip}"


def set_rate_limit_state(request: Request, result: RateLimitResult) -> None:
    """Store the latest rate limit evaluation so middleware can add headers."""

    request.state.rate_limit_result = result


def create_rate_limiter(
    rule: RateLimitRule,
    key_strategy: KeyStrategy,
) -> Callable[..., None]:
    """Create a FastAPI dependency that enforces a fixed-window rate limit."""

    def dependency(
        request: Request,
        db: Session = Depends(get_db),
        storage: InMemoryRateLimitStorage = Depends(get_rate_limit_storage),
    ) -> None:
        key = build_rate_limit_key(request, rule, key_strategy, db)
        result = storage.check_rate_limit(key, rule)
        set_rate_limit_state(request, result)

        if result.allowed:
            return

        headers = {
            "Retry-After": str(result.retry_after),
            "X-RateLimit-Limit": str(result.limit),
            "X-RateLimit-Remaining": str(result.remaining),
            "X-RateLimit-Reset": str(result.reset_at),
        }
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={
                "error": "rate_limit_exceeded",
                "message": f"Rate limit exceeded: {rule.description}",
                "retry_after_seconds": result.retry_after,
            },
            headers=headers,
        )

    return dependency
