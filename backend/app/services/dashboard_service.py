from __future__ import annotations

from collections import defaultdict
from decimal import Decimal

from sqlalchemy import and_, case, extract, func, select
from sqlalchemy.orm import Session

from app.models.transaction import Transaction, TransactionType
from app.models.user import User, UserRole
from app.schemas.dashboard import CategoryBreakdownResponse, MonthlyTrend, RecentTransaction, SummaryResponse


def _dashboard_scope_conditions(current_user: User) -> list:
    conditions = [Transaction.is_deleted.is_(False)]
    if current_user.role != UserRole.analyst:
        conditions.append(Transaction.user_id == current_user.id)
    return conditions


def get_summary(db: Session, current_user: User) -> SummaryResponse:
    condition = and_(*_dashboard_scope_conditions(current_user))
    query = select(
        func.coalesce(func.sum(case((Transaction.type == TransactionType.income, Transaction.amount), else_=0)), 0),
        func.coalesce(func.sum(case((Transaction.type == TransactionType.expense, Transaction.amount), else_=0)), 0),
        func.count(Transaction.id),
    ).where(condition)

    total_income, total_expense, count = db.execute(query).one()
    total_income = Decimal(total_income)
    total_expense = Decimal(total_expense)
    return SummaryResponse(
        total_income=total_income,
        total_expense=total_expense,
        net_balance=total_income - total_expense,
        transaction_count=count,
    )


def get_category_breakdown(db: Session, current_user: User) -> CategoryBreakdownResponse:
    condition = and_(*_dashboard_scope_conditions(current_user))
    query = (
        select(
            Transaction.category,
            Transaction.type,
            func.coalesce(func.sum(Transaction.amount), 0).label("total"),
            func.count(Transaction.id).label("count"),
        )
        .where(condition)
        .group_by(Transaction.category, Transaction.type)
        .order_by(func.sum(Transaction.amount).desc())
    )

    rows = db.execute(query).all()
    grouped: dict[str, list] = defaultdict(list)
    for category, tx_type, total, count in rows:
        grouped[tx_type.value].append({"category": category, "total": Decimal(total), "count": count})
    return CategoryBreakdownResponse(income=grouped["income"], expense=grouped["expense"])


def get_monthly_trends(db: Session, current_user: User, year: int | None = None) -> list[MonthlyTrend]:
    conditions = _dashboard_scope_conditions(current_user)
    if year is not None:
        conditions.append(extract("year", Transaction.date) == year)

    query = (
        select(
            extract("year", Transaction.date).label("year"),
            extract("month", Transaction.date).label("month"),
            func.coalesce(func.sum(case((Transaction.type == TransactionType.income, Transaction.amount), else_=0)), 0).label("income"),
            func.coalesce(func.sum(case((Transaction.type == TransactionType.expense, Transaction.amount), else_=0)), 0).label("expense"),
        )
        .where(and_(*conditions))
        .group_by(extract("year", Transaction.date), extract("month", Transaction.date))
        .order_by(extract("year", Transaction.date).desc(), extract("month", Transaction.date).desc())
    )

    rows = db.execute(query).all()
    trends = []
    for row_year, row_month, income, expense in rows:
        income_decimal = Decimal(income)
        expense_decimal = Decimal(expense)
        trends.append(
            MonthlyTrend(
                month=f"{int(row_year):04d}-{int(row_month):02d}",
                income=income_decimal,
                expense=expense_decimal,
                net=income_decimal - expense_decimal,
            )
        )
    return trends


def get_recent_activity(db: Session, current_user: User, limit: int = 10) -> list[RecentTransaction]:
    query = (
        select(Transaction)
        .where(and_(*_dashboard_scope_conditions(current_user)))
        .order_by(Transaction.date.desc(), Transaction.created_at.desc())
        .limit(limit)
    )

    transactions = list(db.scalars(query))
    return [
        RecentTransaction(
            id=transaction.id,
            amount=transaction.amount,
            type=transaction.type.value,
            category=transaction.category,
            date=transaction.date.isoformat(),
        )
        for transaction in transactions
    ]
