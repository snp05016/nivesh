"""Add compliance tables: audit_log_entries, data_deletion_requests

Adds audit_log_entries + data_deletion_requests so
services/compliance_service.py can support a DPDP-Act-style
right-to-erasure request workflow, consent-withdrawal logging, and a
compliance audit trail.

DEMO ONLY: data_deletion_requests only tracks request/workflow state
(pending|processing|completed|cancelled) — reaching "completed" does not,
by itself, delete any data anywhere in this schema. See
services/compliance_service.py:request_account_deletion() for the explicit
warning.

NOTE: this migration was chained onto m6n7o8p9q0r1 (the loan marketplace
tables migration), the real head at the time this file was written. If
another migration lands on top of m6n7o8p9q0r1 before this one merges,
whichever migration merges second will need to have its down_revision
re-chained to avoid an alembic branch fork.

Revision ID: n7o8p9q0r1s2
Revises: m6n7o8p9q0r1
Create Date: 2026-07-03
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "n7o8p9q0r1s2"
down_revision: Union[str, Sequence[str], None] = "m6n7o8p9q0r1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_tables = set(inspector.get_table_names())

    if "audit_log_entries" not in existing_tables:
        op.create_table(
            "audit_log_entries",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("action", sa.String(length=60), nullable=False),
            sa.Column("details", sa.JSON(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.Column("ip_address", sa.String(length=64), nullable=True),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
        with op.batch_alter_table("audit_log_entries", schema=None) as batch_op:
            batch_op.create_index(batch_op.f("ix_audit_log_entries_id"), ["id"], unique=False)
            batch_op.create_index(batch_op.f("ix_audit_log_entries_user_id"), ["user_id"], unique=False)
            batch_op.create_index(batch_op.f("ix_audit_log_entries_action"), ["action"], unique=False)
            batch_op.create_index(batch_op.f("ix_audit_log_entries_created_at"), ["created_at"], unique=False)

    if "data_deletion_requests" not in existing_tables:
        op.create_table(
            "data_deletion_requests",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("status", sa.String(length=20), nullable=False, server_default="pending"),
            sa.Column("requested_at", sa.DateTime(), nullable=True),
            sa.Column("completed_at", sa.DateTime(), nullable=True),
            sa.Column("reason", sa.Text(), nullable=True),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
            sa.PrimaryKeyConstraint("id"),
            sa.CheckConstraint(
                "status IN ('pending','processing','completed','cancelled')",
                name="ck_data_deletion_request_status",
            ),
        )
        with op.batch_alter_table("data_deletion_requests", schema=None) as batch_op:
            batch_op.create_index(batch_op.f("ix_data_deletion_requests_id"), ["id"], unique=False)
            batch_op.create_index(batch_op.f("ix_data_deletion_requests_user_id"), ["user_id"], unique=False)
            batch_op.create_index(batch_op.f("ix_data_deletion_requests_status"), ["status"], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_tables = set(inspector.get_table_names())

    if "data_deletion_requests" in existing_tables:
        with op.batch_alter_table("data_deletion_requests", schema=None) as batch_op:
            batch_op.drop_index(batch_op.f("ix_data_deletion_requests_status"))
            batch_op.drop_index(batch_op.f("ix_data_deletion_requests_user_id"))
            batch_op.drop_index(batch_op.f("ix_data_deletion_requests_id"))
        op.drop_table("data_deletion_requests")

    if "audit_log_entries" in existing_tables:
        with op.batch_alter_table("audit_log_entries", schema=None) as batch_op:
            batch_op.drop_index(batch_op.f("ix_audit_log_entries_created_at"))
            batch_op.drop_index(batch_op.f("ix_audit_log_entries_action"))
            batch_op.drop_index(batch_op.f("ix_audit_log_entries_user_id"))
            batch_op.drop_index(batch_op.f("ix_audit_log_entries_id"))
        op.drop_table("audit_log_entries")
