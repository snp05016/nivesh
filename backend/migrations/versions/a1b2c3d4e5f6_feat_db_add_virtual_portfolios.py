"""feat(db): add virtual portfolios dividend ledger tax report

Revision ID: a1b2c3d4e5f6
Revises: f0a1b2c3d4e5
Create Date: 2026-06-28 22:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, Sequence[str], None] = "f0a1b2c3d4e5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)

    # --- Add is_virtual to portfolios ---
    existing_cols = [c["name"] for c in inspector.get_columns("portfolios")]
    if "is_virtual" not in existing_cols:
        op.add_column(
            "portfolios",
            sa.Column("is_virtual", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        )

    # --- Add is_virtual to trade_journal ---
    existing_cols = [c["name"] for c in inspector.get_columns("trade_journal")]
    if "is_virtual" not in existing_cols:
        op.add_column(
            "trade_journal",
            sa.Column("is_virtual", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        )

    # --- Create dividend_ledger table ---
    existing_tables = inspector.get_table_names()
    if "dividend_ledger" not in existing_tables:
        op.create_table(
            "dividend_ledger",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
            sa.Column("portfolio_id", sa.Integer(), sa.ForeignKey("portfolios.id"), nullable=True),
            sa.Column("ticker", sa.String(30), nullable=False),
            sa.Column("amount", sa.Float(), nullable=False),
            sa.Column("ex_date", sa.String(20), nullable=True),
            sa.Column("payment_date", sa.String(20), nullable=True),
            sa.Column("created_at", sa.DateTime()),
        )
        op.create_index(
            "ix_dividend_ledger_user_ticker",
            "dividend_ledger",
            ["user_id", "ticker"],
        )

    # --- Create tax_reports table ---
    if "tax_reports" not in existing_tables:
        op.create_table(
            "tax_reports",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
            sa.Column("fy_year", sa.String(20), nullable=False),
            sa.Column("stcg", sa.Float(), default=0.0),
            sa.Column("ltcg", sa.Float(), default=0.0),
            sa.Column("created_at", sa.DateTime()),
            sa.Column("updated_at", sa.DateTime()),
        )
        op.create_unique_constraint(
            "uq_tax_report_user_fy",
            "tax_reports",
            ["user_id", "fy_year"],
        )


def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)

    existing_tables = inspector.get_table_names()

    if "tax_reports" in existing_tables:
        op.drop_table("tax_reports")

    if "dividend_ledger" in existing_tables:
        op.drop_index("ix_dividend_ledger_user_ticker", table_name="dividend_ledger")
        op.drop_table("dividend_ledger")

    existing_cols = [c["name"] for c in inspector.get_columns("trade_journal")]
    if "is_virtual" in existing_cols:
        with op.batch_alter_table("trade_journal") as batch_op:
            batch_op.drop_column("is_virtual")

    existing_cols = [c["name"] for c in inspector.get_columns("portfolios")]
    if "is_virtual" in existing_cols:
        with op.batch_alter_table("portfolios") as batch_op:
            batch_op.drop_column("is_virtual")
