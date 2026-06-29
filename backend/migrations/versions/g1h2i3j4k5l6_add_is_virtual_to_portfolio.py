"""Add is_virtual column to portfolio table and create dividend_ledger / tax_reports tables.

These objects were added to db_models.py but never got Alembic migrations, causing
'no such column: portfolio.is_virtual' errors that break the portfolio endpoint.

Revision ID: g1h2i3j4k5l6
Revises: f0a1b2c3d4e5
Create Date: 2026-06-29
"""

from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy import inspect

from alembic import op

revision: str = "g1h2i3j4k5l6"
down_revision: Union[str, Sequence[str], None] = "f0a1b2c3d4e5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _existing_columns(table_name: str) -> set:
    bind = op.get_bind()
    inspector = inspect(bind)
    return {col["name"] for col in inspector.get_columns(table_name)}


def _existing_tables() -> set:
    bind = op.get_bind()
    inspector = inspect(bind)
    return set(inspector.get_table_names())


def upgrade() -> None:
    # 1. Add is_virtual to portfolio (idempotent)
    if "is_virtual" not in _existing_columns("portfolio"):
        with op.batch_alter_table("portfolio") as batch_op:
            batch_op.add_column(
                sa.Column("is_virtual", sa.Boolean(), nullable=False, server_default="0")
            )

    tables = _existing_tables()

    # 2. Create dividend_ledger if missing
    if "dividend_ledger" not in tables:
        op.create_table(
            "dividend_ledger",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
            sa.Column("portfolio_id", sa.Integer(), nullable=True),
            sa.Column("ticker", sa.String(30), nullable=False),
            sa.Column("amount", sa.Float(), nullable=False),
            sa.Column("ex_date", sa.String(20), nullable=True),
            sa.Column("payment_date", sa.String(20), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=True),
        )
        op.create_index("ix_dividend_ledger_user_ticker", "dividend_ledger", ["user_id", "ticker"])

    # 3. Create tax_reports if missing
    if "tax_reports" not in tables:
        op.create_table(
            "tax_reports",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
            sa.Column("fy_year", sa.String(20), nullable=False),
            sa.Column("stcg", sa.Float(), nullable=True, server_default="0.0"),
            sa.Column("ltcg", sa.Float(), nullable=True, server_default="0.0"),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.Column("updated_at", sa.DateTime(), nullable=True),
            sa.UniqueConstraint("user_id", "fy_year", name="uq_tax_report_user_fy"),
        )


def downgrade() -> None:
    tables = _existing_tables()

    if "tax_reports" in tables:
        op.drop_table("tax_reports")

    if "dividend_ledger" in tables:
        op.drop_index("ix_dividend_ledger_user_ticker", table_name="dividend_ledger")
        op.drop_table("dividend_ledger")

    if "is_virtual" in _existing_columns("portfolio"):
        with op.batch_alter_table("portfolio") as batch_op:
            batch_op.drop_column("is_virtual")
