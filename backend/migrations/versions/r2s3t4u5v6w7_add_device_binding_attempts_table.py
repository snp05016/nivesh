"""Add device_binding_attempts table (SIM-binding fraud-signal audit trail,
MOCK feature)

Adds the DeviceBindingAttempt audit table backing the mock fraud-detection
LOGIC added to services/kyc_consent_service.py::bind_device() — cross-user
device reuse detection and rebind rate limiting. Every bind_device() call
(successful or rejected) inserts one row here; rows are never deleted.

MOCK DATA — simulated for demo purposes, not a real integration. No real
telecom SIM-swap-detection API is called; the fraud signals are heuristics
computed purely over our own DeviceBinding/DeviceBindingAttempt tables.

Revision ID: r2s3t4u5v6w7
Revises: q1r2s3t4u5v6
Create Date: 2026-07-03
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "r2s3t4u5v6w7"
down_revision: Union[str, Sequence[str], None] = "q1r2s3t4u5v6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_tables = set(inspector.get_table_names())

    if "device_binding_attempts" not in existing_tables:
        op.create_table(
            "device_binding_attempts",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("device_id", sa.String(length=120), nullable=False),
            sa.Column("attempted_at", sa.DateTime(), nullable=True),
            sa.Column("outcome", sa.String(length=30), nullable=False),
            sa.Column("reason", sa.Text(), nullable=True),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(
            op.f("ix_device_binding_attempts_id"),
            "device_binding_attempts",
            ["id"],
            unique=False,
        )
        op.create_index(
            op.f("ix_device_binding_attempts_user_id"),
            "device_binding_attempts",
            ["user_id"],
            unique=False,
        )
        op.create_index(
            op.f("ix_device_binding_attempts_device_id"),
            "device_binding_attempts",
            ["device_id"],
            unique=False,
        )
        op.create_index(
            op.f("ix_device_binding_attempts_attempted_at"),
            "device_binding_attempts",
            ["attempted_at"],
            unique=False,
        )


def downgrade() -> None:
    """Downgrade schema."""
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_tables = set(inspector.get_table_names())

    if "device_binding_attempts" in existing_tables:
        op.drop_table("device_binding_attempts")
