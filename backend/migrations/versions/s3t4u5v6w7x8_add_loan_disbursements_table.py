"""Add loan_disbursements table (mock direct lender-borrower fund flow)

Adds loan_disbursements so the MOCK loan marketplace backend
(services/loan_marketplace_service.py:disburse_loan(), routers/finance.py)
can record a mock instant "disbursement" of an approved LoanApplication to
the borrower's primary LinkedBankAccount.

MOCK DATA — simulated for demo purposes, not a real integration. No real
fund transfer, NBFC-to-bank settlement rail, or payment gateway is involved.

Revision ID: s3t4u5v6w7x8
Revises: r2s3t4u5v6w7
Create Date: 2026-07-03

NOTE: down_revision chains onto r2s3t4u5v6w7 (add_device_binding_attempts_table),
which was created concurrently by a sibling agent task in this same worktree
session and also branches off q1r2s3t4u5v6 — chaining after it here keeps a
single linear history instead of a second head.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "s3t4u5v6w7x8"
down_revision: Union[str, Sequence[str], None] = "r2s3t4u5v6w7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_tables = set(inspector.get_table_names())

    if "loan_disbursements" not in existing_tables:
        op.create_table(
            "loan_disbursements",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("loan_application_id", sa.Integer(), nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("linked_bank_account_id", sa.Integer(), nullable=True),
            sa.Column("nbfc_name", sa.String(length=100), nullable=False),
            sa.Column("disbursed_amount", sa.Numeric(precision=14, scale=2), nullable=False),
            sa.Column("status", sa.String(length=20), nullable=False, server_default="completed"),
            sa.Column("disbursed_at", sa.DateTime(), nullable=True),
            sa.Column("failure_reason", sa.Text(), nullable=True),
            sa.ForeignKeyConstraint(["loan_application_id"], ["loan_applications.id"]),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
            sa.ForeignKeyConstraint(["linked_bank_account_id"], ["linked_bank_accounts.id"]),
            sa.PrimaryKeyConstraint("id"),
            sa.CheckConstraint(
                "status IN ('pending','completed','failed')",
                name="ck_loan_disbursement_status",
            ),
        )
        with op.batch_alter_table("loan_disbursements", schema=None) as batch_op:
            batch_op.create_index(batch_op.f("ix_loan_disbursements_id"), ["id"], unique=False)
            batch_op.create_index(
                batch_op.f("ix_loan_disbursements_loan_application_id"), ["loan_application_id"], unique=False
            )
            batch_op.create_index(batch_op.f("ix_loan_disbursements_user_id"), ["user_id"], unique=False)
            batch_op.create_index(
                batch_op.f("ix_loan_disbursements_linked_bank_account_id"),
                ["linked_bank_account_id"],
                unique=False,
            )
            batch_op.create_index(batch_op.f("ix_loan_disbursements_status"), ["status"], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_tables = set(inspector.get_table_names())

    if "loan_disbursements" in existing_tables:
        with op.batch_alter_table("loan_disbursements", schema=None) as batch_op:
            batch_op.drop_index(batch_op.f("ix_loan_disbursements_status"))
            batch_op.drop_index(batch_op.f("ix_loan_disbursements_linked_bank_account_id"))
            batch_op.drop_index(batch_op.f("ix_loan_disbursements_user_id"))
            batch_op.drop_index(batch_op.f("ix_loan_disbursements_loan_application_id"))
            batch_op.drop_index(batch_op.f("ix_loan_disbursements_id"))
        op.drop_table("loan_disbursements")
