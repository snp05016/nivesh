"""Add loan marketplace tables (linked bank accounts, loan offers, loan applications)

Adds linked_bank_accounts, loan_offers, loan_applications so the MOCK loan
marketplace backend (services/loan_marketplace_service.py,
services/credit_bureau_mock_service.py, routers/finance.py) can serve
simulated NBFC loan offers and demo loan applications.

MOCK DATA — simulated for demo purposes, not a real integration.

Revision ID: m6n7o8p9q0r1
Revises: l5m6n7o8p9q0
Create Date: 2026-07-02
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "m6n7o8p9q0r1"
down_revision: Union[str, Sequence[str], None] = "l5m6n7o8p9q0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_tables = set(inspector.get_table_names())

    if "linked_bank_accounts" not in existing_tables:
        op.create_table(
            "linked_bank_accounts",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("bank_name", sa.String(length=100), nullable=False),
            sa.Column("account_type", sa.String(length=20), nullable=False, server_default="savings"),
            sa.Column("masked_account_number", sa.String(length=20), nullable=False),
            sa.Column("ifsc_code", sa.String(length=15), nullable=True),
            sa.Column("is_primary", sa.Boolean(), nullable=False, server_default="1"),
            sa.Column("linked_at", sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint(
                "user_id", "masked_account_number", name="uq_linked_bank_account_user_number"
            ),
        )
        with op.batch_alter_table("linked_bank_accounts", schema=None) as batch_op:
            batch_op.create_index(batch_op.f("ix_linked_bank_accounts_id"), ["id"], unique=False)
            batch_op.create_index(batch_op.f("ix_linked_bank_accounts_user_id"), ["user_id"], unique=False)

    if "loan_offers" not in existing_tables:
        op.create_table(
            "loan_offers",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("nbfc_name", sa.String(length=100), nullable=False),
            sa.Column("loan_type", sa.String(length=20), nullable=False),
            sa.Column("min_amount", sa.Numeric(precision=14, scale=2), nullable=False),
            sa.Column("max_amount", sa.Numeric(precision=14, scale=2), nullable=False),
            sa.Column("interest_rate_pct", sa.Numeric(precision=5, scale=2), nullable=False),
            sa.Column("min_tenure_months", sa.Integer(), nullable=False),
            sa.Column("max_tenure_months", sa.Integer(), nullable=False),
            sa.Column("min_credit_score", sa.Integer(), nullable=False, server_default="650"),
            sa.Column("processing_fee_pct", sa.Numeric(precision=5, scale=2), nullable=False, server_default="1.0"),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default="1"),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.PrimaryKeyConstraint("id"),
        )
        with op.batch_alter_table("loan_offers", schema=None) as batch_op:
            batch_op.create_index(batch_op.f("ix_loan_offers_id"), ["id"], unique=False)
            batch_op.create_index(batch_op.f("ix_loan_offers_loan_type"), ["loan_type"], unique=False)

    if "loan_applications" not in existing_tables:
        op.create_table(
            "loan_applications",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("loan_offer_id", sa.Integer(), nullable=False),
            sa.Column("requested_amount", sa.Numeric(precision=14, scale=2), nullable=False),
            sa.Column("requested_tenure_months", sa.Integer(), nullable=False),
            sa.Column("status", sa.String(length=20), nullable=False, server_default="submitted"),
            sa.Column("mock_credit_score_at_application", sa.Integer(), nullable=True),
            sa.Column("decision_reason", sa.Text(), nullable=True),
            sa.Column("submitted_at", sa.DateTime(), nullable=True),
            sa.Column("decided_at", sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
            sa.ForeignKeyConstraint(["loan_offer_id"], ["loan_offers.id"]),
            sa.PrimaryKeyConstraint("id"),
            sa.CheckConstraint(
                "status IN ('submitted','under_review','approved','rejected','disbursed')",
                name="ck_loan_application_status",
            ),
        )
        with op.batch_alter_table("loan_applications", schema=None) as batch_op:
            batch_op.create_index(batch_op.f("ix_loan_applications_id"), ["id"], unique=False)
            batch_op.create_index(batch_op.f("ix_loan_applications_user_id"), ["user_id"], unique=False)
            batch_op.create_index(
                batch_op.f("ix_loan_applications_loan_offer_id"), ["loan_offer_id"], unique=False
            )
            batch_op.create_index(batch_op.f("ix_loan_applications_status"), ["status"], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_tables = set(inspector.get_table_names())

    if "loan_applications" in existing_tables:
        with op.batch_alter_table("loan_applications", schema=None) as batch_op:
            batch_op.drop_index(batch_op.f("ix_loan_applications_status"))
            batch_op.drop_index(batch_op.f("ix_loan_applications_loan_offer_id"))
            batch_op.drop_index(batch_op.f("ix_loan_applications_user_id"))
            batch_op.drop_index(batch_op.f("ix_loan_applications_id"))
        op.drop_table("loan_applications")

    if "loan_offers" in existing_tables:
        with op.batch_alter_table("loan_offers", schema=None) as batch_op:
            batch_op.drop_index(batch_op.f("ix_loan_offers_loan_type"))
            batch_op.drop_index(batch_op.f("ix_loan_offers_id"))
        op.drop_table("loan_offers")

    if "linked_bank_accounts" in existing_tables:
        with op.batch_alter_table("linked_bank_accounts", schema=None) as batch_op:
            batch_op.drop_index(batch_op.f("ix_linked_bank_accounts_user_id"))
            batch_op.drop_index(batch_op.f("ix_linked_bank_accounts_id"))
        op.drop_table("linked_bank_accounts")
