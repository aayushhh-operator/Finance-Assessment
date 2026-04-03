from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.dependencies import DbSession, get_current_user
from app.models.user import User
from app.rate_limiting import (
    DASHBOARD_CATEGORY_BREAKDOWN_LIMIT,
    DASHBOARD_MONTHLY_TRENDS_LIMIT,
    DASHBOARD_RECENT_LIMIT,
    DASHBOARD_SUMMARY_LIMIT,
    create_rate_limiter,
)
from app.schemas.dashboard import CategoryBreakdownResponse, MonthlyTrend, RecentTransaction, SummaryResponse
from app.services.transaction_service import get_category_breakdown, get_monthly_trends, get_recent_transactions, get_summary

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


@router.get("/summary", response_model=SummaryResponse)
def dashboard_summary(
    db: DbSession,
    _: Annotated[None, Depends(create_rate_limiter(DASHBOARD_SUMMARY_LIMIT, key_strategy="user"))],
    current_user: Annotated[User, Depends(get_current_user)],
) -> SummaryResponse:
    return get_summary(db, current_user)


@router.get("/category-breakdown", response_model=CategoryBreakdownResponse)
def dashboard_category_breakdown(
    db: DbSession,
    _: Annotated[None, Depends(create_rate_limiter(DASHBOARD_CATEGORY_BREAKDOWN_LIMIT, key_strategy="user"))],
    current_user: Annotated[User, Depends(get_current_user)],
) -> CategoryBreakdownResponse:
    return get_category_breakdown(db, current_user)


@router.get("/monthly-trends", response_model=list[MonthlyTrend])
def dashboard_monthly_trends(
    db: DbSession,
    _: Annotated[None, Depends(create_rate_limiter(DASHBOARD_MONTHLY_TRENDS_LIMIT, key_strategy="user"))],
    current_user: Annotated[User, Depends(get_current_user)],
    year: int | None = Query(default=None, ge=2000, le=2100),
) -> list[MonthlyTrend]:
    return get_monthly_trends(db, current_user, year)


@router.get("/recent", response_model=list[RecentTransaction])
def dashboard_recent_transactions(
    db: DbSession,
    _: Annotated[None, Depends(create_rate_limiter(DASHBOARD_RECENT_LIMIT, key_strategy="user"))],
    current_user: Annotated[User, Depends(get_current_user)],
    limit: int = Query(default=10, ge=1, le=50),
) -> list[RecentTransaction]:
    return get_recent_transactions(db, current_user, limit)
