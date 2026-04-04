"""add transaction performance indexes

Revision ID: 002_add_transaction_performance_indexes
Revises: 001_initial_schema
Create Date: 2026-04-05 00:05:00
"""

from alembic import op
import sqlalchemy as sa


revision = "002_add_transaction_performance_indexes"
down_revision = "001_initial_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index(
        "idx_transactions_user_date",
        "transactions",
        ["user_id", "date", "is_deleted"],
        unique=False,
        postgresql_using="btree",
    )
    op.create_index(
        "idx_transactions_date_type",
        "transactions",
        ["date", "type", "is_deleted"],
        unique=False,
        postgresql_using="btree",
    )
    op.create_index(
        "idx_transactions_category_lookup",
        "transactions",
        ["category"],
        unique=False,
        postgresql_using="btree",
    )
    op.create_index(
        "idx_transactions_active",
        "transactions",
        ["is_deleted"],
        unique=False,
        postgresql_where=sa.text("is_deleted = false"),
    )


def downgrade() -> None:
    op.drop_index("idx_transactions_active", table_name="transactions")
    op.drop_index("idx_transactions_category_lookup", table_name="transactions")
    op.drop_index("idx_transactions_date_type", table_name="transactions")
    op.drop_index("idx_transactions_user_date", table_name="transactions")
