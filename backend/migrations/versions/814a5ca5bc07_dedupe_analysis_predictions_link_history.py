"""Dedupe cache-hit prediction rows; one prediction per analysis (DB-17)

Before ML-16 the orchestrator's cache-hit path inserted a new
analysis_predictions row on every call, so one forecast was stored (and later
scored) many times. Prediction rows are now written only for fresh analyses and
carry analysis_history_id, which this revision makes unique.

upgrade: skipped if the table is missing.
  1. Legacy rows (input_asof_date IS NULL, i.e. pre-ML-16): keep MIN(id) per
     (symbol, scan_type, recommendation, confidence_pct, entry_price,
     model_version, calendar date of created_at) and delete the rest.
  2. Rows sharing a non-NULL analysis_history_id: keep MIN(id), delete the rest.
  3. Recreate ix_analysis_predictions_analysis_history_id as UNIQUE (NULLs are
     still allowed many times on SQLite and PostgreSQL).
  The deletes are NOT reversible: take a database backup first (OPS-03).

downgrade: recreates the index as non-unique if it is unique. Deleted
duplicates are not restored.

Revision ID: 814a5ca5bc07
Revises: fa04b9414864
Create Date: 2026-10-11
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "814a5ca5bc07"
down_revision: Union[str, Sequence[str], None] = "fa04b9414864"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TABLE = "analysis_predictions"
_INDEX = "ix_analysis_predictions_analysis_history_id"


def _index(inspector):
    return next((ix for ix in inspector.get_indexes(_TABLE) if ix.get("name") == _INDEX), None)


def _recreate_index(unique: bool) -> None:
    ix = _index(sa.inspect(op.get_bind()))
    if ix is not None and bool(ix.get("unique")) == unique:
        return
    if ix is not None:
        op.drop_index(_INDEX, table_name=_TABLE)
    op.create_index(_INDEX, _TABLE, ["analysis_history_id"], unique=unique)


def upgrade() -> None:
    """Upgrade schema."""
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    if _TABLE not in inspector.get_table_names():
        return

    columns = {c["name"] for c in inspector.get_columns(_TABLE)}
    day = "DATE(created_at)" if conn.dialect.name == "sqlite" else "CAST(created_at AS DATE)"
    legacy = "input_asof_date IS NULL" if "input_asof_date" in columns else "1 = 1"
    conn.execute(sa.text(
        f"DELETE FROM {_TABLE} WHERE {legacy} AND id NOT IN ("
        f"SELECT MIN(id) FROM {_TABLE} WHERE {legacy} "
        f"GROUP BY symbol, scan_type, recommendation, confidence_pct, entry_price, "
        f"model_version, {day})"
    ))
    conn.execute(sa.text(
        f"DELETE FROM {_TABLE} WHERE analysis_history_id IS NOT NULL AND id NOT IN ("
        f"SELECT MIN(id) FROM {_TABLE} WHERE analysis_history_id IS NOT NULL "
        f"GROUP BY analysis_history_id)"
    ))
    _recreate_index(unique=True)


def downgrade() -> None:
    """Downgrade schema."""
    if _TABLE not in sa.inspect(op.get_bind()).get_table_names():
        return
    _recreate_index(unique=False)
