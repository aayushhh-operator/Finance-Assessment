from __future__ import annotations

from datetime import date, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.models.transaction import Transaction
from conftest import TestUserData, create_test_transaction, generate_valid_transaction_data


pytestmark = [pytest.mark.asyncio, pytest.mark.transactions]


async def test_create_transaction_as_admin_succeeds(
    admin_client: AsyncClient,
    viewer_user: TestUserData,
) -> None:
    """Admins should be able to create transactions for another user."""

    payload = generate_valid_transaction_data(user_id=viewer_user.user.id, amount="88.25", type="income")

    response = await admin_client.post("/api/transactions", json=payload)

    assert response.status_code == 201, f"Admin transaction create should succeed, got {response.text}"
    assert response.json()["user_id"] == viewer_user.user.id, "Created transaction should belong to the requested user"


@pytest.mark.permissions
@pytest.mark.parametrize("auth_headers", ["viewer_token", "analyst_token"])
async def test_create_transaction_as_non_admin_returns_403(
    request: pytest.FixtureRequest,
    client: AsyncClient,
    auth_headers: str,
) -> None:
    """Only admins should be allowed to create transactions."""

    headers = request.getfixturevalue(auth_headers)
    response = await client.post("/api/transactions", json=generate_valid_transaction_data(), headers=headers)

    assert response.status_code == 403, f"{auth_headers} should be forbidden from creating transactions, got {response.text}"


async def test_create_transaction_future_date_returns_422(admin_client: AsyncClient) -> None:
    """Future-dated transactions should fail schema validation."""

    payload = generate_valid_transaction_data(date=(date.today() + timedelta(days=1)).isoformat())
    response = await admin_client.post("/api/transactions", json=payload)

    assert response.status_code == 422, f"Future transaction date should return 422, got {response.text}"


@pytest.mark.parametrize("amount", ["-10.00", "0.00"])
async def test_create_transaction_invalid_amount_returns_422(admin_client: AsyncClient, amount: str) -> None:
    """Non-positive amounts should fail validation."""

    payload = generate_valid_transaction_data(amount=amount)
    response = await admin_client.post("/api/transactions", json=payload)

    assert response.status_code == 422, f"Amount {amount} should fail validation, got {response.text}"


async def test_create_transaction_missing_required_fields_returns_422(admin_client: AsyncClient) -> None:
    """Missing transaction fields should produce a normalized validation error."""

    response = await admin_client.post("/api/transactions", json={"category": "Only category"})

    assert response.status_code == 422, f"Missing transaction fields should return 422, got {response.text}"
    assert response.json()["detail"] == "Validation error", "Validation errors should use the custom 422 payload"


async def test_list_transactions_as_viewer_returns_only_own(
    viewer_client: AsyncClient,
    multiple_transactions: list[Transaction],
    viewer_user: TestUserData,
) -> None:
    """Viewers should only see their own active transactions."""

    response = await viewer_client.get("/api/transactions")

    assert response.status_code == 200, f"Viewer list transactions should succeed, got {response.text}"
    items = response.json()["items"]
    assert len(items) == 2, "Viewer should only receive their own two active transactions"
    assert all(item["user_id"] == viewer_user.user.id for item in items), "Viewer should not see other users' records"


async def test_list_transactions_as_analyst_returns_all(
    analyst_client: AsyncClient,
    multiple_transactions: list[Transaction],
) -> None:
    """Analysts should be able to read all active transactions."""

    response = await analyst_client.get("/api/transactions")

    assert response.status_code == 200, f"Analyst list transactions should succeed, got {response.text}"
    assert response.json()["total"] == 4, "Analyst should see all active transactions across users"


async def test_list_transactions_excludes_soft_deleted(
    analyst_client: AsyncClient,
    multiple_transactions: list[Transaction],
    deleted_transaction: Transaction,
) -> None:
    """Soft-deleted transactions should be excluded from list responses."""

    response = await analyst_client.get("/api/transactions")

    assert response.status_code == 200, f"Transaction listing should succeed, got {response.text}"
    ids = {item["id"] for item in response.json()["items"]}
    assert deleted_transaction.id not in ids, "Soft-deleted transaction should not appear in transaction lists"


async def test_list_transactions_pagination_works(
    analyst_client: AsyncClient,
    multiple_transactions: list[Transaction],
) -> None:
    """Pagination should return the requested slice while preserving the total."""

    response = await analyst_client.get("/api/transactions", params={"page": 2, "page_size": 2})

    assert response.status_code == 200, f"Paginated transaction list should succeed, got {response.text}"
    payload = response.json()
    assert payload["page"] == 2, "Response should reflect the requested page number"
    assert len(payload["items"]) == 2, "Second page should contain the remaining two records"
    assert payload["total"] == 4, "Total count should reflect all matching records"


@pytest.mark.parametrize(
    ("params", "expected_total"),
    [({"type": "income"}, 2), ({"category": "Grocer"}, 1)],
)
async def test_list_transactions_filters_work(
    analyst_client: AsyncClient,
    multiple_transactions: list[Transaction],
    params: dict[str, str],
    expected_total: int,
) -> None:
    """Type and category filters should narrow the list correctly."""

    response = await analyst_client.get("/api/transactions", params=params)

    assert response.status_code == 200, f"Filtered transaction list should succeed, got {response.text}"
    assert response.json()["total"] == expected_total, "Filter should return the expected number of records"


async def test_list_transactions_filter_by_date_range(
    analyst_client: AsyncClient,
    multiple_transactions: list[Transaction],
) -> None:
    """Date range filters should return only matching rows."""

    response = await analyst_client.get(
        "/api/transactions",
        params={
            "start_date": (date.today() - timedelta(days=15)).isoformat(),
            "end_date": date.today().isoformat(),
        },
    )

    assert response.status_code == 200, f"Date range filter should succeed, got {response.text}"
    assert response.json()["total"] == 2, "Date range should include only the recent two transactions"


async def test_get_transaction_as_owner_succeeds(
    viewer_client: AsyncClient,
    sample_transaction: Transaction,
) -> None:
    """Owners should be able to fetch their transaction details."""

    response = await viewer_client.get(f"/api/transactions/{sample_transaction.id}")

    assert response.status_code == 200, f"Owner transaction read should succeed, got {response.text}"
    assert response.json()["id"] == sample_transaction.id, "Fetched transaction should match the requested record"


async def test_get_transaction_as_viewer_not_owner_returns_403(
    viewer_client: AsyncClient,
    analyst_user: TestUserData,
    db_session,
) -> None:
    """Viewers should not be able to read another user's transaction."""

    other_transaction = create_test_transaction(db_session, analyst_user.user.id, amount="33.00")
    response = await viewer_client.get(f"/api/transactions/{other_transaction.id}")

    assert response.status_code == 403, f"Viewer should be forbidden from reading another user's transaction, got {response.text}"
    assert response.json()["detail"] == "Not authorized to access this transaction", "Permission error should be explicit"


async def test_get_soft_deleted_transaction_returns_404(
    analyst_client: AsyncClient,
    deleted_transaction: Transaction,
) -> None:
    """Soft-deleted transactions should behave like missing records for reads."""

    response = await analyst_client.get(f"/api/transactions/{deleted_transaction.id}")

    assert response.status_code == 404, f"Soft-deleted transaction should return 404, got {response.text}"
    assert response.json()["detail"] == "Transaction not found", "Deleted transaction detail should match the missing-record message"


async def test_update_transaction_as_admin_succeeds(
    admin_client: AsyncClient,
    sample_transaction: Transaction,
) -> None:
    """Admins should be able to update transaction fields."""

    response = await admin_client.put(
        f"/api/transactions/{sample_transaction.id}",
        json={"amount": "999.99", "category": "Updated Category"},
    )

    assert response.status_code == 200, f"Admin transaction update should succeed, got {response.text}"
    payload = response.json()
    assert payload["amount"] == "999.99", "Updated transaction amount should be returned"
    assert payload["category"] == "Updated Category", "Updated transaction category should be returned"


async def test_update_transaction_as_non_admin_returns_403(
    viewer_client: AsyncClient,
    sample_transaction: Transaction,
) -> None:
    """Non-admins should not be able to update transactions."""

    response = await viewer_client.put(f"/api/transactions/{sample_transaction.id}", json={"amount": "150.00"})

    assert response.status_code == 403, f"Non-admin transaction update should return 403, got {response.text}"


async def test_update_transaction_future_date_returns_422(
    admin_client: AsyncClient,
    sample_transaction: Transaction,
) -> None:
    """Updating a transaction to a future date should fail validation."""

    response = await admin_client.put(
        f"/api/transactions/{sample_transaction.id}",
        json={"date": (date.today() + timedelta(days=2)).isoformat()},
    )

    assert response.status_code == 422, f"Future update date should return 422, got {response.text}"


async def test_delete_transaction_as_admin_soft_deletes(
    admin_client: AsyncClient,
    sample_transaction: Transaction,
    db_session,
) -> None:
    """Deleting a transaction should mark it as deleted instead of removing it."""

    response = await admin_client.delete(f"/api/transactions/{sample_transaction.id}")

    assert response.status_code == 204, f"Admin transaction delete should succeed, got {response.text}"
    stored_transaction = db_session.scalar(select(Transaction).where(Transaction.id == sample_transaction.id))
    assert stored_transaction is not None, "Soft-deleted transaction should remain in the database"
    assert stored_transaction.is_deleted is True, "Soft delete should set the is_deleted flag"


async def test_delete_transaction_as_non_admin_returns_403(
    analyst_client: AsyncClient,
    sample_transaction: Transaction,
) -> None:
    """Non-admins should not be able to soft-delete transactions."""

    response = await analyst_client.delete(f"/api/transactions/{sample_transaction.id}")

    assert response.status_code == 403, f"Non-admin transaction delete should return 403, got {response.text}"


async def test_delete_already_deleted_transaction_returns_404(
    admin_client: AsyncClient,
    deleted_transaction: Transaction,
) -> None:
    """Deleting an already deleted transaction should return 404."""

    response = await admin_client.delete(f"/api/transactions/{deleted_transaction.id}")

    assert response.status_code == 404, f"Deleting an already deleted transaction should return 404, got {response.text}"


async def test_pagination_with_large_page_size(admin_client: AsyncClient) -> None:
    """Page size should be validated against the configured limit."""

    response = await admin_client.get("/api/transactions", params={"page_size": 99999})

    assert response.status_code == 422, f"Large page sizes should be rejected, got {response.text}"


async def test_pagination_with_zero_page(admin_client: AsyncClient) -> None:
    """Page numbers below one should be rejected."""

    response = await admin_client.get("/api/transactions", params={"page": 0})

    assert response.status_code == 422, f"Page=0 should be rejected, got {response.text}"


async def test_dashboard_with_no_data(viewer_client: AsyncClient) -> None:
    """Dashboard summary should return zeroes for empty personal datasets."""

    response = await viewer_client.get("/api/dashboard/summary")

    assert response.status_code == 200, f"Empty dashboard should succeed, got {response.text}"
    assert response.json() == {
        "total_income": "0.00",
        "total_expense": "0.00",
        "net_balance": "0.00",
        "transaction_count": 0,
        "period": "all_time",
    }, "Empty dashboard response should be fully zeroed"
