from sqlalchemy import and_, func, select
from sqlalchemy.orm import Session

from app.exceptions import ForbiddenError, NotFoundError
from app.models.transaction import Transaction
from app.models.user import User, UserRole
from app.schemas.transaction import TransactionCreate, TransactionFilterParams, TransactionUpdate
from app.utils.security import escape_like_pattern


def _active_transaction_condition():
    return Transaction.is_deleted.is_(False)


def get_base_conditions(current_user: User, filters: TransactionFilterParams | None = None) -> list:
    conditions = [_active_transaction_condition()]
    if current_user.role == UserRole.viewer:
        conditions.append(Transaction.user_id == current_user.id)

    if filters is None:
        return conditions

    if filters.type:
        conditions.append(Transaction.type == filters.type)
    if filters.category:
        escaped_category = escape_like_pattern(filters.category)
        conditions.append(Transaction.category.ilike(f"%{escaped_category}%", escape="\\"))
    if filters.start_date:
        conditions.append(Transaction.date >= filters.start_date)
    if filters.end_date:
        conditions.append(Transaction.date <= filters.end_date)
    return conditions


def create_transaction(db: Session, payload: TransactionCreate, current_user: User) -> Transaction:
    if current_user.role != UserRole.admin:
        raise ForbiddenError("Only admins can create transactions")

    owner_id = payload.user_id or current_user.id
    owner = db.get(User, owner_id)
    if owner is None:
        raise NotFoundError("Owner user not found")
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
        raise NotFoundError("Transaction not found")
    return transaction


def ensure_transaction_access(transaction: Transaction, current_user: User) -> None:
    if current_user.role == UserRole.viewer and transaction.user_id != current_user.id:
        raise ForbiddenError("Not authorized to access this transaction")


def list_transactions(db: Session, filters: TransactionFilterParams, current_user: User) -> tuple[list[Transaction], int]:
    conditions = get_base_conditions(current_user, filters)
    predicate = and_(*conditions)
    query = select(Transaction).where(predicate)
    count_query = select(func.count()).select_from(Transaction).where(predicate)

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
