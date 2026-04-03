from __future__ import annotations

import os
import sys
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any, AsyncIterator, Callable

import pytest
import pytest_asyncio
from faker import Faker
from httpx import ASGITransport, AsyncClient
from jose import jwt
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

os.environ["DATABASE_URL"] = "sqlite://"
os.environ["SECRET_KEY"] = "test-secret-key-for-finance-backend-suite"
os.environ["ALGORITHM"] = "HS256"
os.environ["ACCESS_TOKEN_EXPIRE_MINUTES"] = "30"
os.environ["API_V1_PREFIX"] = "/api"
os.environ["PROJECT_NAME"] = "Finance Backend API - Tests"

from app.config import get_settings

get_settings.cache_clear()

from app.database import Base, get_db
from app.main import app
from app.models.transaction import Transaction, TransactionType
from app.models.user import User, UserRole
from app.rate_limiting.dependencies import get_rate_limit_storage
from app.rate_limiting.storage import InMemoryRateLimitStorage
from app.services.auth_service import create_access_token, get_password_hash


@dataclass(slots=True)
class TestUserData:
    """Bundle a test user instance with its plain-text password."""

    __test__ = False

    user: User
    password: str


@dataclass(slots=True)
class RateLimitClock:
    """Controllable clock for rate-limit window tests."""

    current_time: float = 1_700_000_000.0

    def now(self) -> float:
        return self.current_time

    def advance(self, seconds: float) -> None:
        self.current_time += seconds


def get_auth_headers(token: str) -> dict[str, str]:
    """Build bearer authorization headers."""

    return {"Authorization": f"Bearer {token}"}


def generate_valid_transaction_data(user_id: int | None = None, **overrides: Any) -> dict[str, Any]:
    """Generate a valid transaction payload for API tests."""

    payload: dict[str, Any] = {
        "user_id": user_id,
        "amount": "125.50",
        "type": "expense",
        "category": "Utilities",
        "date": date.today().isoformat(),
        "description": "Monthly utility bill",
    }
    payload.update(overrides)
    return payload


def generate_invalid_transaction_data(invalid_field: str) -> dict[str, Any]:
    """Generate transaction payloads with a single invalid field."""

    payload = generate_valid_transaction_data()
    invalid_values: dict[str, Any] = {
        "amount": "-1.00",
        "type": "invalid-type",
        "category": "   ",
        "date": "not-a-date",
        "user_id": 0,
    }
    payload[invalid_field] = invalid_values[invalid_field]
    return payload


def login_payload(email: str, password: str) -> dict[str, str]:
    """Generate OAuth2-compatible login form data."""

    return {"username": email, "password": password}


async def login_user(client: AsyncClient, email: str, password: str) -> str:
    """Authenticate a user and return the JWT access token."""

    response = await client.post("/api/auth/login", data=login_payload(email, password))
    assert response.status_code == 200, f"Expected login to succeed for {email}, got {response.text}"
    return response.json()["access_token"]


def create_test_user(
    db: Session,
    role: UserRole = UserRole.viewer,
    *,
    email: str,
    password: str = "Password123",
    full_name: str | None = None,
    is_active: bool = True,
) -> TestUserData:
    """Create and persist a test user."""

    user = User(
        email=email,
        hashed_password=get_password_hash(password),
        full_name=full_name or email.split("@")[0].replace(".", " ").title(),
        role=role,
        is_active=is_active,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return TestUserData(user=user, password=password)


def create_test_transaction(
    db: Session,
    user_id: int,
    **overrides: Any,
) -> Transaction:
    """Create and persist a test transaction."""

    tx_type = overrides.get("type", TransactionType.expense)
    if isinstance(tx_type, str):
        tx_type = TransactionType(tx_type)

    transaction = Transaction(
        user_id=user_id,
        amount=Decimal(str(overrides.get("amount", "100.00"))),
        type=tx_type,
        category=overrides.get("category", "General"),
        date=overrides.get("date", date.today()),
        description=overrides.get("description", "Test transaction"),
        is_deleted=overrides.get("is_deleted", False),
    )
    db.add(transaction)
    db.commit()
    db.refresh(transaction)
    return transaction


@pytest.fixture
def fake_data() -> Faker:
    """Provide a faker instance for realistic test data."""

    return Faker()


@pytest.fixture
def test_engine():
    """Create an isolated in-memory SQLite engine for a single test."""

    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    Base.metadata.create_all(bind=engine)
    try:
        yield engine
    finally:
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


@pytest.fixture
def db_session(test_engine) -> Session:
    """Provide a database session bound to the test engine."""

    testing_session_local = sessionmaker(
        bind=test_engine,
        autoflush=False,
        autocommit=False,
        expire_on_commit=False,
        class_=Session,
    )
    session = testing_session_local()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture(autouse=True)
def reset_rate_limit_storage() -> InMemoryRateLimitStorage:
    """Reset shared rate limit state before and after each test."""

    storage = get_rate_limit_storage()
    storage.reset()
    yield storage
    storage.reset()


@pytest_asyncio.fixture
async def client(db_session: Session) -> AsyncIterator[AsyncClient]:
    """Create an async test client with the database dependency overridden."""

    async with build_test_client(db_session) as async_client:
        yield async_client


@asynccontextmanager
async def build_test_client(db_session: Session, headers: dict[str, str] | None = None) -> AsyncIterator[AsyncClient]:
    """Construct an async client bound to the shared test database session."""

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test", headers=headers) as async_client:
        yield async_client
    app.dependency_overrides.clear()


@pytest.fixture
def admin_user(db_session: Session) -> TestUserData:
    """Create an admin user with known credentials."""

    return create_test_user(
        db_session,
        role=UserRole.admin,
        email="admin@example.com",
        password="AdminPass123",
        full_name="Admin User",
    )


@pytest.fixture
def analyst_user(db_session: Session) -> TestUserData:
    """Create an analyst user with known credentials."""

    return create_test_user(
        db_session,
        role=UserRole.analyst,
        email="analyst@example.com",
        password="AnalystPass123",
        full_name="Analyst User",
    )


@pytest.fixture
def viewer_user(db_session: Session) -> TestUserData:
    """Create a viewer user with known credentials."""

    return create_test_user(
        db_session,
        role=UserRole.viewer,
        email="viewer@example.com",
        password="ViewerPass123",
        full_name="Viewer User",
    )


@pytest.fixture
def admin_token(admin_user: TestUserData) -> dict[str, str]:
    """Create authorization headers for the admin user."""

    token = create_access_token(subject=admin_user.user.email, role=admin_user.user.role.value)
    return get_auth_headers(token)


@pytest.fixture
def analyst_token(analyst_user: TestUserData) -> dict[str, str]:
    """Create authorization headers for the analyst user."""

    token = create_access_token(subject=analyst_user.user.email, role=analyst_user.user.role.value)
    return get_auth_headers(token)


@pytest.fixture
def viewer_token(viewer_user: TestUserData) -> dict[str, str]:
    """Create authorization headers for the viewer user."""

    token = create_access_token(subject=viewer_user.user.email, role=viewer_user.user.role.value)
    return get_auth_headers(token)


@pytest_asyncio.fixture
async def admin_client(db_session: Session, admin_token: dict[str, str]) -> AsyncIterator[AsyncClient]:
    """Return a client pre-configured with admin auth headers."""

    async with build_test_client(db_session, admin_token) as async_client:
        yield async_client


@pytest_asyncio.fixture
async def analyst_client(db_session: Session, analyst_token: dict[str, str]) -> AsyncIterator[AsyncClient]:
    """Return a client pre-configured with analyst auth headers."""

    async with build_test_client(db_session, analyst_token) as async_client:
        yield async_client


@pytest_asyncio.fixture
async def viewer_client(db_session: Session, viewer_token: dict[str, str]) -> AsyncIterator[AsyncClient]:
    """Return a client pre-configured with viewer auth headers."""

    async with build_test_client(db_session, viewer_token) as async_client:
        yield async_client


@pytest.fixture
def sample_transaction(db_session: Session, viewer_user: TestUserData) -> Transaction:
    """Create a single transaction owned by the viewer."""

    return create_test_transaction(
        db_session,
        viewer_user.user.id,
        amount="250.00",
        type=TransactionType.expense,
        category="Groceries",
        date=date.today() - timedelta(days=3),
        description="Weekly groceries",
    )


@pytest.fixture
def multiple_transactions(
    db_session: Session,
    admin_user: TestUserData,
    analyst_user: TestUserData,
    viewer_user: TestUserData,
) -> list[Transaction]:
    """Create a varied set of transactions for list and dashboard tests."""

    return [
        create_test_transaction(
            db_session,
            viewer_user.user.id,
            amount="1000.00",
            type=TransactionType.income,
            category="Salary",
            date=date.today() - timedelta(days=30),
            description="Monthly salary",
        ),
        create_test_transaction(
            db_session,
            viewer_user.user.id,
            amount="150.00",
            type=TransactionType.expense,
            category="Groceries",
            date=date.today() - timedelta(days=10),
            description="Food shopping",
        ),
        create_test_transaction(
            db_session,
            analyst_user.user.id,
            amount="400.00",
            type=TransactionType.income,
            category="Consulting",
            date=date.today() - timedelta(days=60),
            description="Consulting payout",
        ),
        create_test_transaction(
            db_session,
            admin_user.user.id,
            amount="250.00",
            type=TransactionType.expense,
            category="Rent",
            date=date.today() - timedelta(days=5),
            description="Office rent",
        ),
    ]


@pytest.fixture
def deleted_transaction(db_session: Session, viewer_user: TestUserData) -> Transaction:
    """Create a soft-deleted transaction."""

    return create_test_transaction(
        db_session,
        viewer_user.user.id,
        amount="75.00",
        type=TransactionType.expense,
        category="Archived",
        date=date.today() - timedelta(days=1),
        description="Already deleted",
        is_deleted=True,
    )


@pytest.fixture
def rate_limit_clock(monkeypatch: pytest.MonkeyPatch) -> RateLimitClock:
    """Patch the rate-limit storage clock for deterministic window tests."""

    from app.rate_limiting import storage as storage_module

    clock = RateLimitClock()
    monkeypatch.setattr(storage_module, "time", clock.now)
    return clock


@pytest.fixture
def decode_jwt() -> Callable[[str], dict[str, Any]]:
    """Return a helper that decodes JWTs with the test secret."""

    settings = get_settings()

    def _decode(token: str) -> dict[str, Any]:
        return jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])

    return _decode
