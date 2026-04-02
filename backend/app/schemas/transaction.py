from datetime import date as dt_date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.transaction import TransactionType


class TransactionBase(BaseModel):
    amount: Decimal = Field(gt=0, decimal_places=2, max_digits=10)
    type: TransactionType
    category: str = Field(min_length=1, max_length=100)
    date: dt_date
    description: str | None = Field(default=None, max_length=500)

    @field_validator("category")
    @classmethod
    def strip_category(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Category cannot be empty")
        return value

    @field_validator("description")
    @classmethod
    def normalize_description(cls, value: str | None) -> str | None:
        if value is None:
            return value
        value = value.strip()
        return value or None

    @field_validator("date")
    @classmethod
    def validate_date(cls, value: dt_date) -> dt_date:
        if value > dt_date.today():
            raise ValueError("Transaction date cannot be in the future")
        return value


class TransactionCreate(TransactionBase):
    user_id: int | None = Field(default=None, gt=0)


class TransactionUpdate(BaseModel):
    amount: Decimal | None = Field(default=None, gt=0, decimal_places=2, max_digits=10)
    type: TransactionType | None = None
    category: str | None = Field(default=None, min_length=1, max_length=100)
    date: dt_date | None = None
    description: str | None = Field(default=None, max_length=500)

    @field_validator("category")
    @classmethod
    def strip_optional_category(cls, value: str | None) -> str | None:
        if value is None:
            return value
        value = value.strip()
        if not value:
            raise ValueError("Category cannot be empty")
        return value

    @field_validator("description")
    @classmethod
    def normalize_optional_description(cls, value: str | None) -> str | None:
        if value is None:
            return value
        value = value.strip()
        return value or None

    @field_validator("date")
    @classmethod
    def validate_optional_date(cls, value: dt_date | None) -> dt_date | None:
        if value is not None and value > dt_date.today():
            raise ValueError("Transaction date cannot be in the future")
        return value


class TransactionRead(TransactionBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    created_at: datetime


class PaginatedTransactions(BaseModel):
    items: list[TransactionRead]
    total: int
    page: int
    page_size: int


class TransactionFilterParams(BaseModel):
    type: TransactionType | None = None
    category: str | None = None
    start_date: dt_date | None = None
    end_date: dt_date | None = None
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=10, ge=1, le=100)

    @field_validator("category")
    @classmethod
    def clean_category(cls, value: str | None) -> str | None:
        if value is None:
            return value
        value = value.strip()
        return value or None

    @field_validator("end_date")
    @classmethod
    def validate_date_range(cls, value: dt_date | None, info) -> dt_date | None:
        start_date = info.data.get("start_date")
        if value is not None and start_date is not None and value < start_date:
            raise ValueError("end_date cannot be earlier than start_date")
        return value
