from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import func, select

from app.database import SessionLocal
from app.models.transaction import Transaction, TransactionType
from app.models.user import UserRole
from app.schemas.user import UserCreate
from app.services.user_service import create_user, get_user_by_email


def seed_users() -> None:
    users = [
        UserCreate(email="admin@test.com", password="admin123", full_name="Admin User", role=UserRole.admin),
        UserCreate(email="analyst@test.com", password="analyst123", full_name="Analyst User", role=UserRole.analyst),
        UserCreate(email="viewer@test.com", password="viewer123", full_name="Viewer User", role=UserRole.viewer),
    ]

    transaction_templates = [
        (Decimal("4500.00"), TransactionType.income, "Salary"),
        (Decimal("1200.00"), TransactionType.expense, "Rent"),
        (Decimal("300.00"), TransactionType.expense, "Food"),
        (Decimal("700.00"), TransactionType.income, "Freelance"),
        (Decimal("150.00"), TransactionType.expense, "Utilities"),
    ]

    with SessionLocal() as db:
        created_users = []
        for payload in users:
            user = get_user_by_email(db, payload.email)
            if user is None:
                user = create_user(db, payload)
            created_users.append(user)

        existing_transactions = db.scalar(select(func.count()).select_from(Transaction)) or 0
        if existing_transactions and existing_transactions >= 20:
            return

        start_date = date.today() - timedelta(days=180)
        entries = []
        for index in range(20):
            owner = created_users[index % len(created_users)]
            amount, tx_type, category = transaction_templates[index % len(transaction_templates)]
            entries.append(
                Transaction(
                    user_id=owner.id,
                    amount=amount + Decimal(index * 10),
                    type=tx_type,
                    category=category,
                    date=start_date + timedelta(days=index * 7),
                    description=f"Seeded transaction {index + 1}",
                )
            )

        db.add_all(entries)
        db.commit()


if __name__ == "__main__":
    seed_users()
