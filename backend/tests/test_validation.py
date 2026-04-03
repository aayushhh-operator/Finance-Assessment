from __future__ import annotations

import pytest
from httpx import AsyncClient

from conftest import generate_valid_transaction_data


pytestmark = [pytest.mark.asyncio, pytest.mark.validation]


async def test_invalid_email_format_returns_422(client: AsyncClient) -> None:
    """Invalid emails should be rejected during registration."""

    response = await client.post("/api/auth/register", json={"email": "bad-email", "password": "StrongPass123"})

    assert response.status_code == 422, f"Invalid email should return 422, got {response.text}"


@pytest.mark.parametrize(
    ("payload", "field"),
    [
        ({"amount": "10.00", "type": "invalid", "category": "Food", "date": "2024-01-01"}, "type"),
        ({"amount": "10.00", "type": "income", "category": "Food", "date": "invalid-date"}, "date"),
        ({"amount": "not-a-number", "type": "income", "category": "Food", "date": "2024-01-01"}, "amount"),
    ],
)
async def test_invalid_transaction_fields_return_422(
    admin_client: AsyncClient,
    payload: dict[str, str],
    field: str,
) -> None:
    """Malformed transaction input should return the normalized validation payload."""

    response = await admin_client.post("/api/transactions", json=payload)

    assert response.status_code == 422, f"Invalid field {field} should return 422, got {response.text}"
    assert any(error["field"] == field for error in response.json()["errors"]), f"422 payload should include the {field} field"


async def test_422_response_has_correct_format(client: AsyncClient) -> None:
    """Validation errors should follow the app's normalized response format."""

    response = await client.post("/api/auth/register", json={"email": "still-bad"})

    assert response.status_code == 422, f"Invalid registration payload should return 422, got {response.text}"
    payload = response.json()
    assert payload["detail"] == "Validation error", "Validation response should use the shared detail string"
    assert isinstance(payload["errors"], list) and payload["errors"], "Validation response should include a non-empty errors list"


async def test_extra_fields_are_ignored_on_registration(client: AsyncClient) -> None:
    """Unexpected fields should be ignored under the current Pydantic configuration."""

    response = await client.post(
        "/api/auth/register",
        json={
            "email": "extrafields@example.com",
            "password": "StrongPass123",
            "full_name": "Extra Fields",
            "ignored_field": "value",
        },
    )

    assert response.status_code == 201, f"Extra fields should be ignored, got {response.text}"
    assert "ignored_field" not in response.json(), "Ignored fields should not be echoed back in the response"


async def test_amount_precision_validation(admin_client: AsyncClient) -> None:
    """Amounts with too many decimal places should fail validation."""

    response = await admin_client.post("/api/transactions", json=generate_valid_transaction_data(amount="10.999"))

    assert response.status_code == 422, f"Invalid decimal precision should return 422, got {response.text}"


async def test_end_date_before_start_date_returns_422(analyst_client: AsyncClient) -> None:
    """Invalid date ranges should fail query validation."""

    response = await analyst_client.get(
        "/api/transactions",
        params={"start_date": "2024-01-10", "end_date": "2024-01-01"},
    )

    assert response.status_code == 422, f"Invalid date range should return 422, got {response.text}"
