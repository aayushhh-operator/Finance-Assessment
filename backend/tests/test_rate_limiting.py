from __future__ import annotations

import pytest
from httpx import AsyncClient

from conftest import TestUserData, generate_valid_transaction_data, login_payload


pytestmark = [pytest.mark.asyncio, pytest.mark.rate_limiting]


async def test_login_rate_limit_blocks_after_5_attempts(client: AsyncClient, viewer_user: TestUserData) -> None:
    """The sixth login attempt in the same window should be rate limited."""

    for _ in range(5):
        response = await client.post("/api/auth/login", data=login_payload(viewer_user.user.email, "WrongPassword123"))
        assert response.status_code == 401, "First five invalid login attempts should still hit auth logic"

    blocked_response = await client.post("/api/auth/login", data=login_payload(viewer_user.user.email, "WrongPassword123"))

    assert blocked_response.status_code == 429, f"Sixth login attempt should be rate limited, got {blocked_response.text}"


async def test_login_rate_limit_includes_retry_after_header(client: AsyncClient, viewer_user: TestUserData) -> None:
    """429 responses should include retry metadata."""

    for _ in range(6):
        response = await client.post("/api/auth/login", data=login_payload(viewer_user.user.email, "WrongPassword123"))

    assert response.status_code == 429, f"Expected final login response to be 429, got {response.text}"
    assert response.headers["Retry-After"], "Rate-limited responses should include Retry-After"
    assert response.json()["detail"]["error"] == "rate_limit_exceeded", "429 payload should use the structured rate-limit error"


async def test_transaction_create_rate_limit_enforced(
    admin_client: AsyncClient,
    viewer_user: TestUserData,
) -> None:
    """Transaction creation should stop after the configured per-user limit."""

    for index in range(20):
        response = await admin_client.post(
            "/api/transactions",
            json=generate_valid_transaction_data(
                user_id=viewer_user.user.id,
                amount=f"{index + 1}.00",
                category=f"Category {index}",
            ),
        )
        assert response.status_code == 201, "The first twenty create requests should succeed"

    blocked_response = await admin_client.post(
        "/api/transactions",
        json=generate_valid_transaction_data(user_id=viewer_user.user.id, amount="99.00"),
    )

    assert blocked_response.status_code == 429, f"Twenty-first create request should be rate limited, got {blocked_response.text}"


async def test_dashboard_rate_limit_enforced(analyst_client: AsyncClient) -> None:
    """Dashboard summary requests should respect the stricter dashboard limit."""

    for _ in range(30):
        response = await analyst_client.get("/api/dashboard/summary")
        assert response.status_code == 200, "First thirty dashboard summary requests should succeed"

    blocked_response = await analyst_client.get("/api/dashboard/summary")

    assert blocked_response.status_code == 429, f"Thirty-first dashboard summary request should be rate limited, got {blocked_response.text}"


async def test_rate_limit_resets_after_window(
    client: AsyncClient,
    viewer_user: TestUserData,
    rate_limit_clock,
) -> None:
    """Advancing the fixed window should allow requests again."""

    for _ in range(5):
        response = await client.post("/api/auth/login", data=login_payload(viewer_user.user.email, "WrongPassword123"))
        assert response.status_code == 401, "Requests before the limit should still hit auth logic"

    blocked_response = await client.post("/api/auth/login", data=login_payload(viewer_user.user.email, "WrongPassword123"))
    assert blocked_response.status_code == 429, "Sixth request in the same window should be blocked"

    rate_limit_clock.advance(61)
    reset_response = await client.post("/api/auth/login", data=login_payload(viewer_user.user.email, "WrongPassword123"))

    assert reset_response.status_code == 401, "After the window resets, the request should reach auth validation again"


async def test_rate_limit_headers_present_in_response(client: AsyncClient, viewer_user: TestUserData) -> None:
    """Successful limited requests should still expose rate limit headers."""

    response = await client.post("/api/auth/login", data=login_payload(viewer_user.user.email, "WrongPassword123"))

    assert response.status_code == 401, f"Expected auth failure before the limit is reached, got {response.text}"
    assert response.headers["X-RateLimit-Limit"] == "5", "Responses should expose the request limit"
    assert response.headers["X-RateLimit-Remaining"] == "4", "Responses should expose the remaining request count"
    assert response.headers["X-RateLimit-Reset"], "Responses should expose the reset timestamp"


async def test_different_users_have_separate_limits(
    viewer_client: AsyncClient,
    analyst_client: AsyncClient,
) -> None:
    """User-based limits should be tracked separately per authenticated user."""

    for _ in range(60):
        response = await viewer_client.get("/api/users/me")
        assert response.status_code == 200, "Viewer should be able to use their full user-based limit"

    blocked_response = await viewer_client.get("/api/users/me")
    analyst_response = await analyst_client.get("/api/users/me")

    assert blocked_response.status_code == 429, "Viewer should be rate limited after exhausting their own quota"
    assert analyst_response.status_code == 200, "Another user should still have an independent quota"


async def test_rate_limit_by_ip_for_unauthenticated(client: AsyncClient, viewer_user: TestUserData) -> None:
    """Public auth limits should be scoped by IP address."""

    limited_headers = {"X-Forwarded-For": "203.0.113.10"}
    other_headers = {"X-Forwarded-For": "198.51.100.25"}

    for _ in range(5):
        response = await client.post(
            "/api/auth/login",
            data=login_payload(viewer_user.user.email, "WrongPassword123"),
            headers=limited_headers,
        )
        assert response.status_code == 401, "The first five requests from one IP should not be rate limited"

    blocked_response = await client.post(
        "/api/auth/login",
        data=login_payload(viewer_user.user.email, "WrongPassword123"),
        headers=limited_headers,
    )
    other_ip_response = await client.post(
        "/api/auth/login",
        data=login_payload(viewer_user.user.email, "WrongPassword123"),
        headers=other_headers,
    )

    assert blocked_response.status_code == 429, "The original IP should be rate limited after five attempts"
    assert other_ip_response.status_code == 401, "A different IP should have its own independent limit"
