from __future__ import annotations

from datetime import timedelta

import pytest
from httpx import AsyncClient

from app.services.auth_service import create_access_token
from conftest import TestUserData, create_test_user, login_payload


pytestmark = [pytest.mark.asyncio, pytest.mark.auth]


async def test_register_success_creates_user(client: AsyncClient, db_session) -> None:
    """Successful registration should create a user and hide password data."""

    user_data = {
        "email": "newuser@example.com",
        "password": "SecurePass123",
        "role": "viewer",
        "full_name": "New User",
    }

    response = await client.post("/api/auth/register", json=user_data)

    assert response.status_code == 201, f"Expected successful registration, got {response.text}"
    payload = response.json()
    assert payload["email"] == user_data["email"], "Registered email should match the request payload"
    assert payload["role"] == user_data["role"], "Registered user role should match the requested role"
    assert "password" not in payload, "Registration response must not expose the password"


async def test_register_duplicate_email_returns_400(client: AsyncClient, viewer_user: TestUserData) -> None:
    """Registering an existing email should return a conflict-style validation error."""

    response = await client.post(
        "/api/auth/register",
        json={"email": viewer_user.user.email, "password": "AnotherPass123", "role": "viewer"},
    )

    assert response.status_code == 400, f"Duplicate email should be rejected, got {response.text}"
    assert response.json()["detail"] == "Email already registered", "Duplicate email message should be explicit"


@pytest.mark.parametrize("password", ["short", "allletters", "12345678"])
async def test_register_weak_password_returns_422(client: AsyncClient, password: str) -> None:
    """Weak passwords should fail schema validation."""

    response = await client.post(
        "/api/auth/register",
        json={"email": f"{password}@example.com", "password": password},
    )

    assert response.status_code == 422, f"Weak password {password!r} should fail validation"
    assert response.json()["detail"] == "Validation error", "Weak password should use the normalized 422 format"


async def test_register_invalid_email_format_returns_422(client: AsyncClient) -> None:
    """Invalid email addresses should be rejected by Pydantic."""

    response = await client.post(
        "/api/auth/register",
        json={"email": "not-an-email", "password": "SecurePass123"},
    )

    assert response.status_code == 422, f"Invalid email should return 422, got {response.text}"
    assert response.json()["errors"][0]["field"] == "email", "Validation error should point at the email field"


async def test_register_missing_required_fields_returns_422(client: AsyncClient) -> None:
    """Missing required registration fields should return the normalized error payload."""

    response = await client.post("/api/auth/register", json={})

    assert response.status_code == 422, f"Missing registration fields should return 422, got {response.text}"
    fields = {error["field"] for error in response.json()["errors"]}
    assert {"email", "password"}.issubset(fields), "Both email and password fields should be reported missing"


async def test_register_default_role_is_viewer(client: AsyncClient) -> None:
    """Omitting the role should create a viewer by default."""

    response = await client.post(
        "/api/auth/register",
        json={"email": "defaultrole@example.com", "password": "SecurePass123"},
    )

    assert response.status_code == 201, f"Registration without an explicit role should succeed, got {response.text}"
    assert response.json()["role"] == "viewer", "Default role should be viewer"


async def test_login_success_returns_token(client: AsyncClient, viewer_user: TestUserData) -> None:
    """Valid credentials should return a bearer token."""

    response = await client.post("/api/auth/login", data=login_payload(viewer_user.user.email, viewer_user.password))

    assert response.status_code == 200, f"Expected login success, got {response.text}"
    payload = response.json()
    assert payload["token_type"] == "bearer", "Token type should be bearer"
    assert payload["access_token"], "Access token should be present in the login response"
    assert "finance_access_token=" in response.headers.get("set-cookie", ""), "Login should set an auth cookie"


@pytest.mark.parametrize(
    ("email", "password"),
    [("viewer@example.com", "WrongPass123"), ("missing@example.com", "WrongPass123")],
)
async def test_login_invalid_credentials_returns_401(
    client: AsyncClient,
    viewer_user: TestUserData,
    email: str,
    password: str,
) -> None:
    """Incorrect or unknown credentials should return 401."""

    response = await client.post("/api/auth/login", data=login_payload(email, password))

    assert response.status_code == 401, f"Invalid credentials should return 401, got {response.text}"
    assert response.json()["detail"] == "Invalid credentials", "Invalid login should use the expected error message"


async def test_login_inactive_user_returns_400(client: AsyncClient, db_session) -> None:
    """Inactive users should not be able to log in."""

    inactive_user = create_test_user(
        db_session,
        email="inactive@example.com",
        password="InactivePass123",
        is_active=False,
    )

    response = await client.post("/api/auth/login", data=login_payload(inactive_user.user.email, inactive_user.password))

    assert response.status_code == 400, f"Inactive users should be blocked from login, got {response.text}"
    assert response.json()["detail"] == "Inactive user account", "Inactive login should explain the failure"


async def test_token_contains_valid_claims(client: AsyncClient, viewer_user: TestUserData, decode_jwt) -> None:
    """Returned JWT tokens should include the subject and expiration claims."""

    response = await client.post("/api/auth/login", data=login_payload(viewer_user.user.email, viewer_user.password))

    assert response.status_code == 200, f"Expected login success for token claims test, got {response.text}"
    token = response.json()["access_token"]
    claims = decode_jwt(token)
    assert claims["sub"] == viewer_user.user.email, "JWT subject should be the user email"
    assert "exp" in claims, "JWT should contain an expiration claim"


async def test_expired_token_returns_401(client: AsyncClient, viewer_user: TestUserData) -> None:
    """Expired JWTs should be rejected by authenticated endpoints."""

    expired_token = create_access_token(
        subject=viewer_user.user.email,
        expires_delta=timedelta(minutes=-5),
    )

    response = await client.get("/api/users/me", headers={"Authorization": f"Bearer {expired_token}"})

    assert response.status_code == 401, f"Expired token should return 401, got {response.text}"
    assert response.json()["detail"] == "Could not validate credentials", "Expired token should use auth failure message"


async def test_invalid_token_format_returns_401(client: AsyncClient) -> None:
    """Malformed tokens should be rejected consistently."""

    response = await client.get("/api/users/me", headers={"Authorization": "Bearer not.a.valid.token"})

    assert response.status_code == 401, f"Invalid token should return 401, got {response.text}"
    assert response.json()["detail"] == "Could not validate credentials", "Malformed token should be treated as invalid"


async def test_missing_token_returns_401(client: AsyncClient) -> None:
    """Protected routes should require a bearer token."""

    response = await client.get("/api/users/me")

    assert response.status_code == 401, f"Missing token should return 401, got {response.text}"
    assert response.json()["detail"] == "Not authenticated", "Missing token should trigger the OAuth2 auth error"
