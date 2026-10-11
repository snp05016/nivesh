"""Idempotency-Key columns for loan applications and FD bookings (FINSEC-14)

upgrade: add a nullable idempotency_key column plus a (user_id,
idempotency_key) unique constraint to loan_applications and
fixed_deposit_bookings. NULL keys never collide, so existing rows are
unaffected. Every step is guarded, so databases built by create_all() are
left as is. (The one-completed-disbursement index is 4aa54575a6f3.)

downgrade: drop the constraints and columns if present.

Revision ID: 7b766cb99b86
Revises: 25342fdfb06f
Create Date: 2026-10-11
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "7b766cb99b86"
down_revision: Union[str, Sequence[str], None] = "25342fdfb06f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_IDEM = (
    ("loan_applications", "uq_loan_app_idem"),
    ("fixed_deposit_bookings", "uq_fd_booking_idem"),
)


def _column_names(inspector, table: str) -> set:
    return {c["name"] for c in inspector.get_columns(table)}


def _unique_names(inspector, table: str) -> set:
    return {uc.get("name") for uc in inspector.get_unique_constraints(table)}


def upgrade() -> None:
    """Upgrade schema."""
    inspector = sa.inspect(op.get_bind())
    tables = set(inspector.get_table_names())

    for table, constraint in _IDEM:
        if table not in tables:
            continue
        has_column = "idempotency_key" in _column_names(inspector, table)
        has_unique = constraint in _unique_names(inspector, table)
        if has_column and has_unique:
            continue
        with op.batch_alter_table(table, schema=None) as batch_op:
            if not has_column:
                batch_op.add_column(sa.Column("idempotency_key", sa.String(64), nullable=True))
            if not has_unique:
                batch_op.create_unique_constraint(constraint, ["user_id", "idempotency_key"])


def downgrade() -> None:
    """Downgrade schema."""
    inspector = sa.inspect(op.get_bind())
    tables = set(inspector.get_table_names())

    for table, constraint in _IDEM:
        if table not in tables:
            continue
        has_unique = constraint in _unique_names(inspector, table)
        has_column = "idempotency_key" in _column_names(inspector, table)
        if not (has_unique or has_column):
            continue
        with op.batch_alter_table(table, schema=None) as batch_op:
            if has_unique:
                batch_op.drop_constraint(constraint, type_="unique")
            if has_column:
                batch_op.drop_column("idempotency_key")
