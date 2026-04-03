from __future__ import annotations

from datetime import date, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.models.transaction import Transaction
from conftest import TestUserData, create_test_transaction, generate_valid_transaction_data


pytestmark = [pytest.mark.asyncio, pytest.mark.business_rules]


async def test_cannot_create_future_dated_transaction(admin_client: AsyncClient) -> None:
    """Future-dated transactions should fail validation."""

    response = await admin_client.post(
        "/api/transactions",
        json=generate_valid_transaction_data(date=(date.today() + timedelta(days=1)).isoformat()),
    )

    assert response.status_code == 422, f"Future-dated transaction should return 422, got {response.text}"


async def test_cannot_update_to_future_date(admin_client: AsyncClient, sample_transaction) -> None:
    """Updating a transaction to a future date should fail validation."""

    response = await admin_client.put(
        f"/api/transactions/{sample_transaction.id}",
        json={"date": (date.today() + timedelta(days=3)).isoformat()},
    )

    assert response.status_code == 422, f"Future-dated update should return 422, got {response.text}"


async def test_user_cannot_deactivate_self(admin_client: AsyncClient, admin_user: TestUserData) -> None:
    """Self-deactivation should be blocked by business logic."""

    response = await admin_client.put(f"/api/users/{admin_user.user.id}/status", json={"is_active": False})

    assert response.status_code == 400, f"Self-deactivation should return 400, got {response.text}"


async def test_email_must_be_unique(client: AsyncClient, viewer_user: TestUserData) -> None:
    """Duplicate registration emails should return a 400 business-rule error."""

    response = await client.post(
        "/api/auth/register",
        json={"email": viewer_user.user.email, "password": "AnotherPass123"},
    )

    assert response.status_code == 400, f"Duplicate email should return 400, got {response.text}"


@pytest.mark.parametrize("password", ["password", "12345678", "short1"])
async def test_password_meets_strength_requirements(client: AsyncClient, password: str) -> None:
    """Passwords must include at least one letter, one number, and eight characters."""

    response = await client.post(
        "/api/auth/register",
        json={"email": f"{password}@example.com", "password": password},
    )

    assert response.status_code == 422, f"Weak password {password!r} should return 422, got {response.text}"


@pytest.mark.parametrize("amount", ["-5.00", "0.00"])
async def test_amounts_must_be_positive(admin_client: AsyncClient, amount: str) -> None:
    """Transaction amounts must be positive."""

    response = await admin_client.post("/api/transactions", json=generate_valid_transaction_data(amount=amount))

    assert response.status_code == 422, f"Non-positive amount {amount} should return 422, got {response.text}"


async def test_soft_delete_preserves_data(
    admin_client: AsyncClient,
    sample_transaction,
    db_session,
) -> None:
    """Soft delete should keep the row in the database."""

    response = await admin_client.delete(f"/api/transactions/{sample_transaction.id}")

    assert response.status_code == 204, f"Soft delete should succeed, got {response.text}"
    stored = db_session.scalar(select(Transaction).where(Transaction.id == sample_transaction.id))
    assert stored is not None and stored.is_deleted is True, "Soft delete should preserve the row and set is_deleted"


async def test_deleted_transactions_excluded_from_lists_and_dashboards(
    analyst_client: AsyncClient,
    viewer_user: TestUserData,
    db_session,
) -> None:
    """Deleted transactions should not appear in lists or dashboards."""

    create_test_transaction(db_session, viewer_user.user.id, amount="100.00", type="income", is_deleted=True)
    list_response = await analyst_client.get("/api/transactions")
    dashboard_response = await analyst_client.get("/api/dashboard/summary")

    assert list_response.json()["total"] == 0, "Deleted transactions should not appear in transaction lists"
    assert dashboard_response.json()["transaction_count"] == 0, "Deleted transactions should not affect dashboard counts"


async def test_can_create_transaction_for_today(admin_client: AsyncClient) -> None:
    """Today's date should be allowed."""

    response = await admin_client.post("/api/transactions", json=generate_valid_transaction_data(date=date.today().isoformat()))

    assert response.status_code == 201, f"Today's date should be accepted, got {response.text}"


async def test_can_create_transaction_for_past(admin_client: AsyncClient) -> None:
    """Past transaction dates should be allowed."""

    response = await admin_client.post(
        "/api/transactions",
        json=generate_valid_transaction_data(date=(date.today() - timedelta(days=30)).isoformat()),
    )

    assert response.status_code == 201, f"Past date should be accepted, got {response.text}"
