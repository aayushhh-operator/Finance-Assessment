from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response, status

from app.dependencies import DbSession, get_current_user, require_roles
from app.models.user import User, UserRole
from app.rate_limiting import (
    CREATE_TRANSACTION_LIMIT,
    DELETE_TRANSACTION_LIMIT,
    LIST_TRANSACTIONS_LIMIT,
    READ_TRANSACTION_LIMIT,
    UPDATE_TRANSACTION_LIMIT,
    create_rate_limiter,
)
from app.schemas.transaction import PaginatedTransactions, TransactionCreate, TransactionFilterParams, TransactionRead, TransactionUpdate
from app.services.transaction_service import (
    create_transaction,
    delete_transaction,
    ensure_transaction_access,
    get_transaction_or_404,
    list_transactions,
    update_transaction,
)

router = APIRouter(prefix="/transactions", tags=["Transactions"])


@router.post("", response_model=TransactionRead, status_code=status.HTTP_201_CREATED)
def create_transaction_endpoint(
    payload: TransactionCreate,
    _: Annotated[None, Depends(create_rate_limiter(CREATE_TRANSACTION_LIMIT, key_strategy="user"))],
    db: DbSession,
    current_user: Annotated[User, Depends(require_roles(UserRole.admin))],
) -> TransactionRead:
    return create_transaction(db, payload, current_user)


@router.get("", response_model=PaginatedTransactions)
def read_transactions(
    db: DbSession,
    _: Annotated[None, Depends(create_rate_limiter(LIST_TRANSACTIONS_LIMIT, key_strategy="user"))],
    current_user: Annotated[User, Depends(get_current_user)],
    type: str | None = Query(default=None),
    category: str | None = Query(default=None),
    start_date: date | None = Query(default=None),
    end_date: date | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=10, ge=1, le=100),
) -> PaginatedTransactions:
    filters = TransactionFilterParams(
        type=type,
        category=category,
        start_date=start_date,
        end_date=end_date,
        page=page,
        page_size=page_size,
    )
    items, total = list_transactions(db, filters, current_user)
    return PaginatedTransactions(items=items, total=total, page=filters.page, page_size=filters.page_size)


@router.get("/{transaction_id}", response_model=TransactionRead)
def read_transaction(
    transaction_id: int,
    db: DbSession,
    _: Annotated[None, Depends(create_rate_limiter(READ_TRANSACTION_LIMIT, key_strategy="user"))],
    current_user: Annotated[User, Depends(get_current_user)],
) -> TransactionRead:
    transaction = get_transaction_or_404(db, transaction_id)
    ensure_transaction_access(transaction, current_user)
    return transaction


@router.put("/{transaction_id}", response_model=TransactionRead)
def update_transaction_endpoint(
    transaction_id: int,
    payload: TransactionUpdate,
    _: Annotated[None, Depends(create_rate_limiter(UPDATE_TRANSACTION_LIMIT, key_strategy="user"))],
    db: DbSession,
    current_user: Annotated[User, Depends(require_roles(UserRole.admin))],
) -> TransactionRead:
    transaction = get_transaction_or_404(db, transaction_id)
    return update_transaction(db, transaction, payload)


@router.delete("/{transaction_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_transaction_endpoint(
    transaction_id: int,
    db: DbSession,
    _: Annotated[None, Depends(create_rate_limiter(DELETE_TRANSACTION_LIMIT, key_strategy="user"))],
    current_user: Annotated[User, Depends(require_roles(UserRole.admin))],
) -> Response:
    transaction = get_transaction_or_404(db, transaction_id)
    delete_transaction(db, transaction)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
