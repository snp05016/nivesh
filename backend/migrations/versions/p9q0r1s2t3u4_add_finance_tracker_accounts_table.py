"""Add finance_tracker_accounts table (Finance Tracker MOCK linked accounts)

Adds finance_tracker_accounts so the MOCK Finance Tracker backend
(services/finance_tracker_service.py, routers/finance.py) can serve the
iOS Finance Tracker tab's linked-account balances, sync timestamps, and
spend-category breakdown.

MOCK DATA — simulated for demo purposes, not a real integration. No real
account-aggregator / bank-linking (OAuth/Plaid-style) flow is wired to this
table. Functionally distinct from linked_bank_accounts (Loan Marketplace,
see m6n7o8p9q0r1_add_loan_marketplace_tables.py) — that table has no
balance column and backs a different feature.

Revision ID: p9q0r1s2t3u4
Revises: o8p9q0r1s2t3
Create Date: 2026-07-03
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "p9q0r1s2t3u4"
down_revision: Union[str, Sequence[str], None] = "o8p9q0r1s2t3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_tables = set(inspector.get_table_names())

    if "finance_tracker_accounts" not in existing_tables:
        op.create_table(
            "finance_tracker_accounts",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("bank_name", sa.String(length=100), nullable=False),
            sa.Column("account_type", sa.String(length=20), nullable=False, server_default="savings"),
            sa.Column("masked_account_number", sa.String(length=20), nullable=False),
            sa.Column("balance", sa.Numeric(14, 2), nullable=False, server_default="0"),
            sa.Column("last_synced_at", sa.DateTime(), nullable=True),
            sa.Column("is_mock", sa.Boolean(), nullable=False, server_default="1"),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
            sa.PrimaryKeyConstraint("id"),
            sa.CheckConstraint(
                "account_type IN ('savings','current','credit_card','wallet')",
                name="ck_finance_tracker_account_type",
            ),
        )
        with op.batch_alter_table("finance_tracker_accounts", schema=None) as batch_op:
            batch_op.create_index(
                batch_op.f("ix_finance_tracker_accounts_id"), ["id"], unique=False
            )
            batch_op.create_index(
                batch_op.f("ix_finance_tracker_accounts_user_id"), ["user_id"], unique=False
            )


def downgrade() -> None:
    """Downgrade schema."""
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_tables = set(inspector.get_table_names())

    if "finance_tracker_accounts" in existing_tables:
        with op.batch_alter_table("finance_tracker_accounts", schema=None) as batch_op:
            batch_op.drop_index(batch_op.f("ix_finance_tracker_accounts_user_id"))
            batch_op.drop_index(batch_op.f("ix_finance_tracker_accounts_id"))
        op.drop_table("finance_tracker_accounts")
