from __future__ import annotations

import pytest
from httpx import AsyncClient

from conftest import TestUserData, create_test_user


pytestmark = [pytest.mark.asyncio]


@pytest.mark.auth
async def test_get_current_user_returns_own_info(viewer_client: AsyncClient, viewer_user: TestUserData) -> None:
    """Authenticated users should be able to fetch their own profile."""

    response = await viewer_client.get("/api/users/me")

    assert response.status_code == 200, f"Current user endpoint should succeed, got {response.text}"
    assert response.json()["email"] == viewer_user.user.email, "Users/me should return the authenticated user"


@pytest.mark.auth
async def test_get_current_user_without_token_returns_401(client: AsyncClient) -> None:
    """Anonymous requests should be denied."""

    response = await client.get("/api/users/me")

    assert response.status_code == 401, f"Unauthenticated request should return 401, got {response.text}"


@pytest.mark.permissions
async def test_list_users_as_admin_returns_all_users(
    admin_client: AsyncClient,
    admin_user: TestUserData,
    analyst_user: TestUserData,
    viewer_user: TestUserData,
) -> None:
    """Admins should be able to list all users."""

    response = await admin_client.get("/api/users")

    assert response.status_code == 200, f"Admin list users should succeed, got {response.text}"
    emails = {item["email"] for item in response.json()}
    assert {admin_user.user.email, analyst_user.user.email, viewer_user.user.email}.issubset(
        emails
    ), "Admin user listing should include all seeded users"


@pytest.mark.permissions
@pytest.mark.parametrize("auth_headers", ["viewer_token", "analyst_token"])
async def test_list_users_as_non_admin_returns_403(
    request: pytest.FixtureRequest,
    client: AsyncClient,
    auth_headers: str,
) -> None:
    """Non-admin roles should not be allowed to list all users."""

    headers = request.getfixturevalue(auth_headers)
    response = await client.get("/api/users", headers=headers)

    assert response.status_code == 403, f"{auth_headers} should not be allowed to list users, got {response.text}"
    assert response.json()["detail"] == "Forbidden", "Non-admin user listing should be forbidden"


@pytest.mark.permissions
async def test_update_user_role_as_admin_succeeds(
    admin_client: AsyncClient,
    viewer_user: TestUserData,
) -> None:
    """Admins should be able to change another user's role."""

    response = await admin_client.put(f"/api/users/{viewer_user.user.id}/role", json={"role": "analyst"})

    assert response.status_code == 200, f"Admin role update should succeed, got {response.text}"
    assert response.json()["role"] == "analyst", "Role update response should contain the new role"


@pytest.mark.permissions
async def test_update_user_role_as_non_admin_returns_403(
    viewer_client: AsyncClient,
    admin_user: TestUserData,
) -> None:
    """Non-admin users should not be able to change roles."""

    response = await viewer_client.put(f"/api/users/{admin_user.user.id}/role", json={"role": "viewer"})

    assert response.status_code == 403, f"Non-admin role change should return 403, got {response.text}"


@pytest.mark.validation
async def test_update_user_role_invalid_role_returns_422(
    admin_client: AsyncClient,
    viewer_user: TestUserData,
) -> None:
    """Invalid roles should fail schema validation."""

    response = await admin_client.put(f"/api/users/{viewer_user.user.id}/role", json={"role": "superuser"})

    assert response.status_code == 422, f"Invalid role should return 422, got {response.text}"
    assert response.json()["detail"] == "Validation error", "Invalid role should use normalized 422 payload"


@pytest.mark.permissions
async def test_update_user_status_as_admin_succeeds(
    admin_client: AsyncClient,
    viewer_user: TestUserData,
) -> None:
    """Admins should be able to deactivate another user."""

    response = await admin_client.put(f"/api/users/{viewer_user.user.id}/status", json={"is_active": False})

    assert response.status_code == 200, f"Admin status update should succeed, got {response.text}"
    assert response.json()["is_active"] is False, "User status should reflect the requested inactive state"


@pytest.mark.permissions
async def test_update_user_status_as_non_admin_returns_403(
    analyst_client: AsyncClient,
    viewer_user: TestUserData,
) -> None:
    """Non-admin users should not be able to change user status."""

    response = await analyst_client.put(f"/api/users/{viewer_user.user.id}/status", json={"is_active": False})

    assert response.status_code == 403, f"Non-admin status change should return 403, got {response.text}"


@pytest.mark.business_rules
async def test_deactivate_self_returns_400(admin_client: AsyncClient, admin_user: TestUserData) -> None:
    """Users should not be able to deactivate themselves."""

    response = await admin_client.put(f"/api/users/{admin_user.user.id}/status", json={"is_active": False})

    assert response.status_code == 400, f"Self-deactivation should return 400, got {response.text}"
    assert response.json()["detail"] == "User cannot deactivate themselves", "Business rule message should be explicit"


@pytest.mark.permissions
@pytest.mark.parametrize("path_suffix,payload", [("role", {"role": "viewer"}), ("status", {"is_active": False})])
async def test_update_nonexistent_user_returns_404(
    admin_client: AsyncClient,
    path_suffix: str,
    payload: dict[str, object],
) -> None:
    """Updating a missing user should return 404."""

    response = await admin_client.put(f"/api/users/99999/{path_suffix}", json=payload)

    assert response.status_code == 404, f"Missing user update should return 404, got {response.text}"
    assert response.json()["detail"] == "User not found", "Missing user response should use the expected detail"
