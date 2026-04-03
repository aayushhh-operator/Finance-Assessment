from __future__ import annotations

from datetime import date, timedelta

import pytest
from httpx import AsyncClient

from app.models.transaction import Transaction, TransactionType
from conftest import TestUserData, create_test_transaction


pytestmark = [pytest.mark.asyncio, pytest.mark.dashboard]


def _seed_dashboard_data(db_session, admin_user: TestUserData, analyst_user: TestUserData, viewer_user: TestUserData) -> list[Transaction]:
    """Create a predictable dashboard dataset spanning users and months."""

    return [
        create_test_transaction(
            db_session,
            viewer_user.user.id,
            amount="1000.00",
            type=TransactionType.income,
            category="Salary",
            date=date.today() - timedelta(days=30),
        ),
        create_test_transaction(
            db_session,
            viewer_user.user.id,
            amount="250.00",
            type=TransactionType.expense,
            category="Groceries",
            date=date.today() - timedelta(days=25),
        ),
        create_test_transaction(
            db_session,
            viewer_user.user.id,
            amount="100.00",
            type=TransactionType.expense,
            category="Transport",
            date=date.today() - timedelta(days=5),
        ),
        create_test_transaction(
            db_session,
            analyst_user.user.id,
            amount="600.00",
            type=TransactionType.income,
            category="Consulting",
            date=date.today() - timedelta(days=60),
        ),
        create_test_transaction(
            db_session,
            admin_user.user.id,
            amount="300.00",
            type=TransactionType.expense,
            category="Rent",
            date=date.today() - timedelta(days=10),
        ),
    ]


async def test_summary_as_viewer_shows_personal_data(
    viewer_client: AsyncClient,
    db_session,
    admin_user: TestUserData,
    analyst_user: TestUserData,
    viewer_user: TestUserData,
) -> None:
    """Viewer summaries should only include that viewer's active transactions."""

    _seed_dashboard_data(db_session, admin_user, analyst_user, viewer_user)
    response = await viewer_client.get("/api/dashboard/summary")

    assert response.status_code == 200, f"Viewer dashboard summary should succeed, got {response.text}"
    payload = response.json()
    assert payload["total_income"] == "1000.00", "Viewer income summary should include only viewer income"
    assert payload["total_expense"] == "350.00", "Viewer expense summary should include only viewer expenses"
    assert payload["net_balance"] == "650.00", "Viewer net balance should be income minus expense"
    assert payload["transaction_count"] == 3, "Viewer summary should count only viewer transactions"


async def test_summary_as_analyst_shows_system_wide_data(
    analyst_client: AsyncClient,
    db_session,
    admin_user: TestUserData,
    analyst_user: TestUserData,
    viewer_user: TestUserData,
) -> None:
    """Analysts should see system-wide dashboard numbers."""

    _seed_dashboard_data(db_session, admin_user, analyst_user, viewer_user)
    response = await analyst_client.get("/api/dashboard/summary")

    assert response.status_code == 200, f"Analyst dashboard summary should succeed, got {response.text}"
    payload = response.json()
    assert payload["total_income"] == "1600.00", "Analyst summary should aggregate all active income"
    assert payload["total_expense"] == "650.00", "Analyst summary should aggregate all active expense"
    assert payload["transaction_count"] == 5, "Analyst summary should count all active transactions"


async def test_summary_as_admin_shows_personal_data(
    admin_client: AsyncClient,
    db_session,
    admin_user: TestUserData,
    analyst_user: TestUserData,
    viewer_user: TestUserData,
) -> None:
    """Admins currently receive a personal dashboard scope."""

    _seed_dashboard_data(db_session, admin_user, analyst_user, viewer_user)
    response = await admin_client.get("/api/dashboard/summary")

    assert response.status_code == 200, f"Admin dashboard summary should succeed, got {response.text}"
    payload = response.json()
    assert payload["total_income"] == "0.00", "Admin personal dashboard should not include other users' income"
    assert payload["total_expense"] == "300.00", "Admin personal dashboard should include only admin expense"
    assert payload["transaction_count"] == 1, "Admin personal dashboard should include only admin transactions"


async def test_summary_excludes_soft_deleted_transactions(
    analyst_client: AsyncClient,
    db_session,
    admin_user: TestUserData,
    analyst_user: TestUserData,
    viewer_user: TestUserData,
) -> None:
    """Soft-deleted rows should not affect dashboard summary totals."""

    _seed_dashboard_data(db_session, admin_user, analyst_user, viewer_user)
    create_test_transaction(
        db_session,
        viewer_user.user.id,
        amount="900.00",
        type=TransactionType.income,
        category="Deleted Income",
        date=date.today() - timedelta(days=2),
        is_deleted=True,
    )

    response = await analyst_client.get("/api/dashboard/summary")

    assert response.status_code == 200, f"Dashboard summary should succeed, got {response.text}"
    assert response.json()["total_income"] == "1600.00", "Deleted transactions must not contribute to totals"


async def test_category_breakdown_groups_correctly(
    analyst_client: AsyncClient,
    db_session,
    admin_user: TestUserData,
    analyst_user: TestUserData,
    viewer_user: TestUserData,
) -> None:
    """Category breakdown should group totals by category and type."""

    _seed_dashboard_data(db_session, admin_user, analyst_user, viewer_user)
    create_test_transaction(
        db_session,
        viewer_user.user.id,
        amount="50.00",
        type=TransactionType.expense,
        category="Groceries",
        date=date.today() - timedelta(days=1),
    )

    response = await analyst_client.get("/api/dashboard/category-breakdown")

    assert response.status_code == 200, f"Category breakdown should succeed, got {response.text}"
    payload = response.json()
    groceries = next(item for item in payload["expense"] if item["category"] == "Groceries")
    assert groceries["total"] == "300.00", "Category totals should aggregate matching expense rows"
    assert groceries["count"] == 2, "Category count should reflect the number of grouped transactions"


async def test_category_breakdown_respects_role_scope(
    viewer_client: AsyncClient,
    db_session,
    admin_user: TestUserData,
    analyst_user: TestUserData,
    viewer_user: TestUserData,
) -> None:
    """Viewer category breakdown should exclude categories owned by other users."""

    _seed_dashboard_data(db_session, admin_user, analyst_user, viewer_user)
    response = await viewer_client.get("/api/dashboard/category-breakdown")

    assert response.status_code == 200, f"Viewer category breakdown should succeed, got {response.text}"
    categories = {item["category"] for item in response.json()["expense"]}
    assert "Rent" not in categories, "Viewer breakdown should not expose admin categories"


async def test_monthly_trends_groups_by_month(
    analyst_client: AsyncClient,
    db_session,
    admin_user: TestUserData,
    analyst_user: TestUserData,
    viewer_user: TestUserData,
) -> None:
    """Monthly trends should aggregate amounts into year-month buckets."""

    _seed_dashboard_data(db_session, admin_user, analyst_user, viewer_user)
    response = await analyst_client.get("/api/dashboard/monthly-trends")

    assert response.status_code == 200, f"Monthly trends should succeed, got {response.text}"
    assert len(response.json()) >= 2, "Monthly trends should contain at least two monthly buckets for seeded data"


async def test_monthly_trends_filters_by_year(
    analyst_client: AsyncClient,
    db_session,
    admin_user: TestUserData,
    analyst_user: TestUserData,
    viewer_user: TestUserData,
) -> None:
    """Year filtering should return only matching trend rows."""

    current_year = date.today().year
    _seed_dashboard_data(db_session, admin_user, analyst_user, viewer_user)
    create_test_transaction(
        db_session,
        analyst_user.user.id,
        amount="700.00",
        type=TransactionType.income,
        category="Legacy",
        date=date(current_year - 1, 12, 15),
    )

    response = await analyst_client.get("/api/dashboard/monthly-trends", params={"year": current_year})

    assert response.status_code == 200, f"Year-filtered trends should succeed, got {response.text}"
    assert all(item["month"].startswith(str(current_year)) for item in response.json()), "Year filter should remove other years"


async def test_recent_activity_returns_latest_first_and_respects_limit(
    analyst_client: AsyncClient,
    db_session,
    admin_user: TestUserData,
    analyst_user: TestUserData,
    viewer_user: TestUserData,
) -> None:
    """Recent activity should be ordered newest-first and respect the limit parameter."""

    _seed_dashboard_data(db_session, admin_user, analyst_user, viewer_user)
    create_test_transaction(
        db_session,
        viewer_user.user.id,
        amount="55.00",
        type=TransactionType.expense,
        category="Coffee",
        date=date.today(),
    )

    response = await analyst_client.get("/api/dashboard/recent", params={"limit": 2})

    assert response.status_code == 200, f"Recent activity should succeed, got {response.text}"
    items = response.json()
    assert len(items) == 2, "Recent endpoint should respect the requested result limit"
    assert items[0]["category"] == "Coffee", "Recent endpoint should return the newest transaction first"


async def test_dashboard_with_no_transactions_returns_zeros(analyst_client: AsyncClient) -> None:
    """Empty datasets should still return a valid zeroed dashboard response."""

    response = await analyst_client.get("/api/dashboard/summary")

    assert response.status_code == 200, f"Empty dashboard summary should succeed, got {response.text}"
    assert response.json() == {
        "total_income": "0.00",
        "total_expense": "0.00",
        "net_balance": "0.00",
        "transaction_count": 0,
        "period": "all_time",
    }, "Empty dashboard should return zero totals and the default period"
