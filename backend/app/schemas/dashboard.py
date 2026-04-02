from decimal import Decimal

from pydantic import BaseModel


class SummaryResponse(BaseModel):
    total_income: Decimal
    total_expense: Decimal
    net_balance: Decimal
    transaction_count: int
    period: str = "all_time"


class CategoryBucket(BaseModel):
    category: str
    total: Decimal
    count: int


class CategoryBreakdownResponse(BaseModel):
    income: list[CategoryBucket]
    expense: list[CategoryBucket]


class MonthlyTrend(BaseModel):
    month: str
    income: Decimal
    expense: Decimal
    net: Decimal


class RecentTransaction(BaseModel):
    id: int
    amount: Decimal
    type: str
    category: str
    date: str
