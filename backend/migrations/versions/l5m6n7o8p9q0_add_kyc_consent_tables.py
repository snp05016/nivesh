"""Add KYC consent + device-binding tables (loan marketplace)

Adds kyc_consents, device_bindings so services/kyc_consent_service.py can
persist consent grants/revocations and a MOCK "SIM-binding"-style device
consent check for the loan marketplace KYC flow. No real telecom or credit
bureau integration is involved — see kyc_consent_service.py docstring.

Revision ID: l5m6n7o8p9q0
Revises: k4l5m6n7o8p9
Create Date: 2026-07-02
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "l5m6n7o8p9q0"
down_revision: Union[str, Sequence[str], None] = "k4l5m6n7o8p9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_tables = set(inspector.get_table_names())

    if "kyc_consents" not in existing_tables:
        op.create_table(
            "kyc_consents",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("consent_type", sa.String(length=40), nullable=False),
            sa.Column("granted", sa.Boolean(), nullable=False, server_default="0"),
            sa.Column("granted_at", sa.DateTime(), nullable=True),
            sa.Column("ip_address", sa.String(length=64), nullable=True),
            sa.Column("revoked_at", sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
        with op.batch_alter_table("kyc_consents", schema=None) as batch_op:
            batch_op.create_index(batch_op.f("ix_kyc_consents_id"), ["id"], unique=False)
            batch_op.create_index(batch_op.f("ix_kyc_consents_user_id"), ["user_id"], unique=False)
            batch_op.create_index(batch_op.f("ix_kyc_consents_consent_type"), ["consent_type"], unique=False)

    if "device_bindings" not in existing_tables:
        op.create_table(
            "device_bindings",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("device_id", sa.String(length=120), nullable=False),
            sa.Column("bound_at", sa.DateTime(), nullable=True),
            sa.Column("is_primary", sa.Boolean(), nullable=False, server_default="1"),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("user_id", "device_id", name="uq_device_binding_user_device"),
        )
        with op.batch_alter_table("device_bindings", schema=None) as batch_op:
            batch_op.create_index(batch_op.f("ix_device_bindings_id"), ["id"], unique=False)
            batch_op.create_index(batch_op.f("ix_device_bindings_user_id"), ["user_id"], unique=False)
            batch_op.create_index(batch_op.f("ix_device_bindings_device_id"), ["device_id"], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_tables = set(inspector.get_table_names())

    if "device_bindings" in existing_tables:
        with op.batch_alter_table("device_bindings", schema=None) as batch_op:
            batch_op.drop_index(batch_op.f("ix_device_bindings_device_id"))
            batch_op.drop_index(batch_op.f("ix_device_bindings_user_id"))
            batch_op.drop_index(batch_op.f("ix_device_bindings_id"))
        op.drop_table("device_bindings")

    if "kyc_consents" in existing_tables:
        with op.batch_alter_table("kyc_consents", schema=None) as batch_op:
            batch_op.drop_index(batch_op.f("ix_kyc_consents_consent_type"))
            batch_op.drop_index(batch_op.f("ix_kyc_consents_user_id"))
            batch_op.drop_index(batch_op.f("ix_kyc_consents_id"))
        op.drop_table("kyc_consents")
