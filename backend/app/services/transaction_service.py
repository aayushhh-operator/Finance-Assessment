from collections import defaultdict
from decimal import Decimal

from fastapi import HTTPException, status
from sqlalchemy import and_, case, extract, func, select
from sqlalchemy.orm import Session

from app.models.transaction import Transaction, TransactionType
from app.models.user import User, UserRole
from app.schemas.dashboard import CategoryBreakdownResponse, MonthlyTrend, RecentTransaction, SummaryResponse
from app.schemas.transaction import TransactionCreate, TransactionFilterParams, TransactionUpdate


def _active_transaction_condition():
    return Transaction.is_deleted.is_(False)


def _transaction_scope_query(current_user: User):
    query = select(Transaction).where(_active_transaction_condition())
    if current_user.role == UserRole.viewer:
        query = query.where(Transaction.user_id == current_user.id)
    return query


def _dashboard_scope_condition(current_user: User):
    conditions = [_active_transaction_condition()]
    if current_user.role == UserRole.analyst:
        return and_(*conditions)
    conditions.append(Transaction.user_id == current_user.id)
    return and_(*conditions)


def create_transaction(db: Session, payload: TransactionCreate, current_user: User) -> Transaction:
    owner_id = payload.user_id or current_user.id
    owner = db.get(User, owner_id)
    if owner is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Owner user not found")
    transaction = Transaction(
        user_id=owner_id,
        amount=payload.amount,
        type=payload.type,
        category=payload.category,
        date=payload.date,
        description=payload.description,
    )
    db.add(transaction)
    db.commit()
    db.refresh(transaction)
    return transaction


def get_transaction_or_404(db: Session, transaction_id: int) -> Transaction:
    transaction = db.scalar(select(Transaction).where(Transaction.id == transaction_id, _active_transaction_condition()))
    if not transaction:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Transaction not found")
    return transaction


def ensure_transaction_access(transaction: Transaction, current_user: User) -> None:
    if current_user.role == UserRole.viewer and transaction.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to access this transaction")


def list_transactions(db: Session, filters: TransactionFilterParams, current_user: User) -> tuple[list[Transaction], int]:
    query = _transaction_scope_query(current_user)
    count_query = select(func.count()).select_from(Transaction).where(_active_transaction_condition())

    conditions = []
    if filters.type:
        conditions.append(Transaction.type == filters.type)
    if filters.category:
        conditions.append(Transaction.category.ilike(f"%{filters.category}%"))
    if filters.start_date:
        conditions.append(Transaction.date >= filters.start_date)
    if filters.end_date:
        conditions.append(Transaction.date <= filters.end_date)

    if conditions:
        predicate = and_(*conditions)
        query = query.where(predicate)
        count_query = count_query.where(predicate)

    query = query.order_by(Transaction.date.desc(), Transaction.created_at.desc())
    query = query.offset((filters.page - 1) * filters.page_size).limit(filters.page_size)

    items = list(db.scalars(query))
    total = db.scalar(count_query) or 0
    return items, total


def update_transaction(db: Session, transaction: Transaction, payload: TransactionUpdate) -> Transaction:
    updates = payload.model_dump(exclude_unset=True)
    for field, value in updates.items():
        setattr(transaction, field, value)
    db.add(transaction)
    db.commit()
    db.refresh(transaction)
    return transaction


def delete_transaction(db: Session, transaction: Transaction) -> None:
    transaction.is_deleted = True
    db.add(transaction)
    db.commit()


def get_summary(db: Session, current_user: User) -> SummaryResponse:
    condition = _dashboard_scope_condition(current_user)
    query = select(
        func.coalesce(func.sum(case((Transaction.type == TransactionType.income, Transaction.amount), else_=0)), 0),
        func.coalesce(func.sum(case((Transaction.type == TransactionType.expense, Transaction.amount), else_=0)), 0),
        func.count(Transaction.id),
    )
    query = query.where(condition)

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
    condition = _dashboard_scope_condition(current_user)
    query = select(
        Transaction.category,
        Transaction.type,
        func.coalesce(func.sum(Transaction.amount), 0).label("total"),
        func.count(Transaction.id).label("count"),
    ).group_by(Transaction.category, Transaction.type).order_by(func.sum(Transaction.amount).desc())
    query = query.where(condition)

    rows = db.execute(query).all()
    grouped: dict[str, list] = defaultdict(list)
    for category, tx_type, total, count in rows:
        grouped[tx_type.value].append({"category": category, "total": Decimal(total), "count": count})
    return CategoryBreakdownResponse(income=grouped["income"], expense=grouped["expense"])


def get_monthly_trends(db: Session, current_user: User, year: int | None = None) -> list[MonthlyTrend]:
    query = select(
        extract("year", Transaction.date).label("year"),
        extract("month", Transaction.date).label("month"),
        func.coalesce(func.sum(case((Transaction.type == TransactionType.income, Transaction.amount), else_=0)), 0).label("income"),
        func.coalesce(func.sum(case((Transaction.type == TransactionType.expense, Transaction.amount), else_=0)), 0).label("expense"),
    ).group_by(extract("year", Transaction.date), extract("month", Transaction.date)).order_by(
        extract("year", Transaction.date).desc(), extract("month", Transaction.date).desc()
    )

    conditions = []
    scope = _dashboard_scope_condition(current_user)
    conditions.append(scope)
    if year is not None:
        conditions.append(extract("year", Transaction.date) == year)
    if conditions:
        query = query.where(and_(*conditions))

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


def get_recent_transactions(db: Session, current_user: User, limit: int = 10) -> list[RecentTransaction]:
    query = select(Transaction).order_by(
        Transaction.date.desc(), Transaction.created_at.desc()
    ).limit(limit)
    condition = _dashboard_scope_condition(current_user)
    query = query.where(condition)

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
