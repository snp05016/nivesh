"""Prediction logging provenance and natural key (ML-16)

Adds nullable provenance columns to analysis_predictions (ml_direction,
ml_p_up, input_asof_date, weights_version, ml_fallback_used, target_date) and
the partial unique index uq_ap_symbol_asof_scan_model on
(symbol, input_asof_date, scan_type, model_version) WHERE input_asof_date IS
NOT NULL. Legacy rows have no input_asof_date, so the index never conflicts with
them and no destructive dedupe is needed.

upgrade: skipped if the table is missing; each column and the index are added
only if absent.

downgrade: drops the index and the columns only if present.

Revision ID: 2b3e6056a7c7
Revises: f32cf73ca308
Create Date: 2026-10-11
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "2b3e6056a7c7"
down_revision: Union[str, Sequence[str], None] = "f32cf73ca308"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TABLE = "analysis_predictions"
_INDEX = "uq_ap_symbol_asof_scan_model"
_WHERE = "input_asof_date IS NOT NULL"
_COLUMNS = (
    ("ml_direction", sa.Integer()),
    ("ml_p_up", sa.Float()),
    ("input_asof_date", sa.Date()),
    ("weights_version", sa.String(length=40)),
    ("ml_fallback_used", sa.Boolean()),
    ("target_date", sa.Date()),
)


def _index_exists(inspector) -> bool:
    return any(ix.get("name") == _INDEX for ix in inspector.get_indexes(_TABLE))


def upgrade() -> None:
    """Upgrade schema."""
    inspector = sa.inspect(op.get_bind())
    if _TABLE not in inspector.get_table_names():
        return

    existing = {c["name"] for c in inspector.get_columns(_TABLE)}
    missing = [(name, type_) for name, type_ in _COLUMNS if name not in existing]
    if missing:
        with op.batch_alter_table(_TABLE, schema=None) as batch_op:
            for name, type_ in missing:
                batch_op.add_column(sa.Column(name, type_, nullable=True))

    if not _index_exists(sa.inspect(op.get_bind())):
        op.create_index(
            _INDEX,
            _TABLE,
            ["symbol", "input_asof_date", "scan_type", "model_version"],
            unique=True,
            sqlite_where=sa.text(_WHERE),
            postgresql_where=sa.text(_WHERE),
        )


def downgrade() -> None:
    """Downgrade schema."""
    inspector = sa.inspect(op.get_bind())
    if _TABLE not in inspector.get_table_names():
        return

    if _index_exists(inspector):
        op.drop_index(_INDEX, table_name=_TABLE)

    existing = {c["name"] for c in inspector.get_columns(_TABLE)}
    present = [name for name, _ in reversed(_COLUMNS) if name in existing]
    if present:
        with op.batch_alter_table(_TABLE, schema=None) as batch_op:
            for name in present:
                batch_op.drop_column(name)
