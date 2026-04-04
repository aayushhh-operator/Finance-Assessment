from __future__ import annotations

import pytest
from httpx import AsyncClient

from conftest import TestUserData, create_test_transaction, generate_valid_transaction_data


pytestmark = [pytest.mark.asyncio, pytest.mark.permissions]


async def test_viewer_can_read_own_transactions(
    viewer_client: AsyncClient,
    sample_transaction,
) -> None:
    """Viewers should be able to access their own transaction detail."""

    response = await viewer_client.get(f"/api/transactions/{sample_transaction.id}")

    assert response.status_code == 200, f"Viewer should read their own transaction, got {response.text}"


async def test_viewer_cannot_read_others_transactions(
    viewer_client: AsyncClient,
    analyst_user: TestUserData,
    db_session,
) -> None:
    """Viewers should be denied access to another user's transaction."""

    analyst_transaction = create_test_transaction(db_session, analyst_user.user.id, amount="25.00")
    response = await viewer_client.get(f"/api/transactions/{analyst_transaction.id}")

    assert response.status_code == 403, f"Viewer should not read another user's transaction, got {response.text}"


@pytest.mark.parametrize("method", ["post", "put", "delete"])
async def test_viewer_cannot_modify_transactions(
    viewer_client: AsyncClient,
    viewer_user: TestUserData,
    sample_transaction,
    method: str,
) -> None:
    """Viewers should not be allowed to create, update, or delete transactions."""

    if method == "post":
        response = await viewer_client.post("/api/transactions", json=generate_valid_transaction_data(user_id=viewer_user.user.id))
    elif method == "put":
        response = await viewer_client.put(f"/api/transactions/{sample_transaction.id}", json={"amount": "20.00"})
    else:
        response = await viewer_client.delete(f"/api/transactions/{sample_transaction.id}")

    assert response.status_code == 403, f"Viewer {method} should be forbidden, got {response.text}"


@pytest.mark.parametrize("path,json_body", [("/api/users", None), ("/api/users/1/role", {"role": "admin"})])
async def test_viewer_cannot_manage_users(
    viewer_client: AsyncClient,
    path: str,
    json_body: dict[str, str] | None,
) -> None:
    """Viewers should not be able to list users or change roles."""

    if json_body is None:
        response = await viewer_client.get(path)
    else:
        response = await viewer_client.put(path, json=json_body)

    assert response.status_code == 403, f"Viewer should not access {path}, got {response.text}"


async def test_analyst_can_read_all_transactions(
    analyst_client: AsyncClient,
    multiple_transactions,
) -> None:
    """Analysts should have read access to the full transaction list."""

    response = await analyst_client.get("/api/transactions")

    assert response.status_code == 200, f"Analyst list transactions should succeed, got {response.text}"
    assert response.json()["total"] == 4, "Analyst should see all active transactions"


@pytest.mark.parametrize("method", ["post", "put", "delete"])
async def test_analyst_cannot_modify_transactions(
    analyst_client: AsyncClient,
    admin_user: TestUserData,
    sample_transaction,
    method: str,
) -> None:
    """Analysts should remain read-only for transaction mutations."""

    if method == "post":
        response = await analyst_client.post("/api/transactions", json=generate_valid_transaction_data(user_id=admin_user.user.id))
    elif method == "put":
        response = await analyst_client.put(f"/api/transactions/{sample_transaction.id}", json={"amount": "20.00"})
    else:
        response = await analyst_client.delete(f"/api/transactions/{sample_transaction.id}")

    assert response.status_code == 403, f"Analyst {method} should be forbidden, got {response.text}"


async def test_analyst_sees_system_wide_dashboard(
    analyst_client: AsyncClient,
    db_session,
    admin_user: TestUserData,
    viewer_user: TestUserData,
) -> None:
    """Analyst dashboard scope should aggregate all users' data."""

    create_test_transaction(db_session, viewer_user.user.id, amount="100.00", type="income")
    create_test_transaction(db_session, admin_user.user.id, amount="50.00", type="expense")
    response = await analyst_client.get("/api/dashboard/summary")

    assert response.status_code == 200, f"Analyst dashboard summary should succeed, got {response.text}"
    assert response.json()["transaction_count"] == 2, "Analyst dashboard should include system-wide activity"


async def test_admin_can_manage_everything(
    admin_client: AsyncClient,
    viewer_user: TestUserData,
    sample_transaction,
) -> None:
    """Admins should be able to create, update, delete, and manage users."""

    create_response = await admin_client.post(
        "/api/transactions",
        json=generate_valid_transaction_data(user_id=viewer_user.user.id, amount="77.00"),
    )
    update_response = await admin_client.put(f"/api/transactions/{sample_transaction.id}", json={"amount": "44.00"})
    delete_response = await admin_client.delete(f"/api/transactions/{sample_transaction.id}")
    manage_response = await admin_client.put(f"/api/users/{viewer_user.user.id}/role", json={"role": "analyst"})

    assert create_response.status_code == 201, f"Admin create should succeed, got {create_response.text}"
    assert update_response.status_code == 200, f"Admin update should succeed, got {update_response.text}"
    assert delete_response.status_code == 204, f"Admin delete should succeed, got {delete_response.text}"
    assert manage_response.status_code == 200, f"Admin user management should succeed, got {manage_response.text}"


async def test_viewer_pagination_total_count_accuracy(
    viewer_client: AsyncClient,
    db_session,
    admin_user: TestUserData,
    viewer_user: TestUserData,
) -> None:
    """Viewer totals should only count rows they are allowed to access."""

    for index in range(50):
        create_test_transaction(
            db_session,
            admin_user.user.id,
            amount="100.00",
            type="income",
            category="Admin Seed",
            description=f"Admin transaction {index}",
        )

    for index in range(5):
        create_test_transaction(
            db_session,
            viewer_user.user.id,
            amount="50.00",
            type="expense",
            category="Viewer Seed",
            description=f"Viewer transaction {index}",
        )

    response = await viewer_client.get("/api/transactions", params={"page": 1, "page_size": 10})

    assert response.status_code == 200, f"Viewer pagination should succeed, got {response.text}"
    data = response.json()
    assert data["total"] == 5, f"Expected viewer total=5 but got {data['total']}"
    assert len(data["items"]) == 5, "Viewer should only receive their accessible rows"
