"""Add fixed_deposit_schemes and fixed_deposit_bookings tables (Fixed
Deposit Marketplace MOCK feature)

Adds the tables backing the MOCK Fixed Deposit marketplace
(services/fixed_deposit_service.py, routers/fixed_deposits.py): FD scheme
discovery/comparison, an FD calculator, and mock-instant-settlement FD
bookings gated by the existing KYC consent + device-binding primitives
(services/kyc_consent_service.py — reused, not modified).

MOCK DATA — simulated for demo purposes, not a real integration. No real
bank/NBFC FD issuer rate-card feed or UPI/net-banking payment gateway is
called anywhere behind these tables.

Revision ID: q1r2s3t4u5v6
Revises: p9q0r1s2t3u4
Create Date: 2026-07-03
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "q1r2s3t4u5v6"
down_revision: Union[str, Sequence[str], None] = "p9q0r1s2t3u4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_tables = set(inspector.get_table_names())

    if "fixed_deposit_schemes" not in existing_tables:
        op.create_table(
            "fixed_deposit_schemes",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("issuer_name", sa.String(length=100), nullable=False),
            sa.Column("min_tenure_months", sa.Integer(), nullable=False),
            sa.Column("max_tenure_months", sa.Integer(), nullable=False),
            sa.Column("min_amount", sa.Numeric(14, 2), nullable=False),
            sa.Column("max_amount", sa.Numeric(14, 2), nullable=False),
            sa.Column("interest_rate_pct", sa.Numeric(5, 2), nullable=False),
            sa.Column("senior_citizen_bonus_pct", sa.Numeric(5, 2), nullable=False, server_default="0.50"),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default="1"),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.PrimaryKeyConstraint("id"),
        )
        with op.batch_alter_table("fixed_deposit_schemes", schema=None) as batch_op:
            batch_op.create_index(
                batch_op.f("ix_fixed_deposit_schemes_id"), ["id"], unique=False
            )

    existing_tables = set(sa.inspect(conn).get_table_names())
    if "fixed_deposit_bookings" not in existing_tables:
        op.create_table(
            "fixed_deposit_bookings",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("scheme_id", sa.Integer(), nullable=False),
            sa.Column("principal_amount", sa.Numeric(14, 2), nullable=False),
            sa.Column("tenure_months", sa.Integer(), nullable=False),
            sa.Column("interest_rate_pct", sa.Numeric(5, 2), nullable=False),
            sa.Column("maturity_amount", sa.Numeric(14, 2), nullable=False),
            sa.Column("payment_method", sa.String(length=20), nullable=False),
            sa.Column("status", sa.String(length=20), nullable=False, server_default="confirmed"),
            sa.Column("decision_reason", sa.Text(), nullable=True),
            sa.Column("booked_at", sa.DateTime(), nullable=True),
            sa.Column("matures_at", sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
            sa.ForeignKeyConstraint(["scheme_id"], ["fixed_deposit_schemes.id"]),
            sa.PrimaryKeyConstraint("id"),
            sa.CheckConstraint(
                "status IN ('pending','confirmed','failed')",
                name="ck_fixed_deposit_booking_status",
            ),
            sa.CheckConstraint(
                "payment_method IN ('upi','net_banking')",
                name="ck_fixed_deposit_booking_payment_method",
            ),
        )
        with op.batch_alter_table("fixed_deposit_bookings", schema=None) as batch_op:
            batch_op.create_index(
                batch_op.f("ix_fixed_deposit_bookings_id"), ["id"], unique=False
            )
            batch_op.create_index(
                batch_op.f("ix_fixed_deposit_bookings_user_id"), ["user_id"], unique=False
            )
            batch_op.create_index(
                batch_op.f("ix_fixed_deposit_bookings_scheme_id"), ["scheme_id"], unique=False
            )


def downgrade() -> None:
    """Downgrade schema."""
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_tables = set(inspector.get_table_names())

    if "fixed_deposit_bookings" in existing_tables:
        with op.batch_alter_table("fixed_deposit_bookings", schema=None) as batch_op:
            batch_op.drop_index(batch_op.f("ix_fixed_deposit_bookings_scheme_id"))
            batch_op.drop_index(batch_op.f("ix_fixed_deposit_bookings_user_id"))
            batch_op.drop_index(batch_op.f("ix_fixed_deposit_bookings_id"))
        op.drop_table("fixed_deposit_bookings")

    existing_tables = set(sa.inspect(conn).get_table_names())
    if "fixed_deposit_schemes" in existing_tables:
        with op.batch_alter_table("fixed_deposit_schemes", schema=None) as batch_op:
            batch_op.drop_index(batch_op.f("ix_fixed_deposit_schemes_id"))
        op.drop_table("fixed_deposit_schemes")
