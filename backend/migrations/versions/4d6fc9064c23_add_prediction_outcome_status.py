"""Prediction outcome lifecycle columns (ML-15)

Adds outcome_status (pending / abstain / scored / unresolvable, server default
'pending'), outcome_attempts (server default 0), benchmark_return_30d and
hit_vs_benchmark_30d and the target-horizon label columns (actual_return_target,
hit_direction_target, brier_score_target) to analysis_predictions, plus the index
ix_ap_outcome_status. Existing rows take the server defaults; no data rewrite.

upgrade: skipped if the table is missing; each column and the index are added
only if absent.

downgrade: drops the index and the columns only if present.

Revision ID: 4d6fc9064c23
Revises: 2b3e6056a7c7
Create Date: 2026-10-11
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "4d6fc9064c23"
down_revision: Union[str, Sequence[str], None] = "2b3e6056a7c7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TABLE = "analysis_predictions"
_INDEX = "ix_ap_outcome_status"


def _columns():
    return (
        sa.Column("outcome_status", sa.String(length=20), nullable=False, server_default="pending"),
        sa.Column("outcome_attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("benchmark_return_30d", sa.Float(), nullable=True),
        sa.Column("hit_vs_benchmark_30d", sa.Boolean(), nullable=True),
        sa.Column("actual_return_target", sa.Float(), nullable=True),
        sa.Column("hit_direction_target", sa.Boolean(), nullable=True),
        sa.Column("brier_score_target", sa.Float(), nullable=True),
    )


def _index_exists(inspector) -> bool:
    return any(ix.get("name") == _INDEX for ix in inspector.get_indexes(_TABLE))


def upgrade() -> None:
    """Upgrade schema."""
    inspector = sa.inspect(op.get_bind())
    if _TABLE not in inspector.get_table_names():
        return

    existing = {c["name"] for c in inspector.get_columns(_TABLE)}
    missing = [col for col in _columns() if col.name not in existing]
    if missing:
        with op.batch_alter_table(_TABLE, schema=None) as batch_op:
            for col in missing:
                batch_op.add_column(col)

    if not _index_exists(sa.inspect(op.get_bind())):
        op.create_index(_INDEX, _TABLE, ["outcome_status"])


def downgrade() -> None:
    """Downgrade schema."""
    inspector = sa.inspect(op.get_bind())
    if _TABLE not in inspector.get_table_names():
        return

    if _index_exists(inspector):
        op.drop_index(_INDEX, table_name=_TABLE)

    existing = {c["name"] for c in inspector.get_columns(_TABLE)}
    present = [col.name for col in reversed(_columns()) if col.name in existing]
    if present:
        with op.batch_alter_table(_TABLE, schema=None) as batch_op:
            for name in present:
                batch_op.drop_column(name)
