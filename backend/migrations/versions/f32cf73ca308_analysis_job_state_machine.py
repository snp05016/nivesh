"""Analysis job state machine: one active job per user and scan_type (DB-11)

Adds the partial unique index uq_analysis_jobs_active_user_scan on
analysis_jobs(user_id, scan_type) WHERE status IN ('QUEUED', 'RUNNING'), the
database backstop for create_job(), and widens job_id to VARCHAR(36) for full
uuid4 ids.

upgrade: skipped if the table is missing. Older duplicate active rows (same
user_id and scan_type) are marked FAILED, keeping the newest. job_id is widened
only where the length is enforced (not SQLite) and still shorter than 36. The
index is created only if absent.

downgrade: drops the index if present. job_id stays VARCHAR(36): narrowing it
would truncate the ids already issued.

Revision ID: f32cf73ca308
Revises: 6646d6dc6c12
Create Date: 2026-10-11
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "f32cf73ca308"
down_revision: Union[str, Sequence[str], None] = "6646d6dc6c12"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TABLE = "analysis_jobs"
_INDEX = "uq_analysis_jobs_active_user_scan"
_WHERE = "status IN ('QUEUED', 'RUNNING')"


def _index_exists(inspector) -> bool:
    return any(ix.get("name") == _INDEX for ix in inspector.get_indexes(_TABLE))


def upgrade() -> None:
    """Upgrade schema."""
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    if _TABLE not in inspector.get_table_names():
        return

    conn.execute(sa.text(
        "UPDATE analysis_jobs SET status = 'FAILED', finished_at = CURRENT_TIMESTAMP, "
        "error = 'Superseded by a newer active job (migration f32cf73ca308)' "
        "WHERE status IN ('QUEUED', 'RUNNING') AND user_id IS NOT NULL AND EXISTS ("
        "  SELECT 1 FROM analysis_jobs newer"
        "  WHERE newer.user_id = analysis_jobs.user_id"
        "    AND newer.scan_type = analysis_jobs.scan_type"
        "    AND newer.status IN ('QUEUED', 'RUNNING')"
        "    AND (newer.created_at > analysis_jobs.created_at"
        "         OR (newer.created_at = analysis_jobs.created_at"
        "             AND newer.job_id > analysis_jobs.job_id)))"
    ))

    if conn.dialect.name != "sqlite":
        job_id = next(c for c in inspector.get_columns(_TABLE) if c["name"] == "job_id")
        length = getattr(job_id["type"], "length", None)
        if length is not None and length < 36:
            op.alter_column(_TABLE, "job_id", type_=sa.String(36),
                            existing_type=sa.String(length), existing_nullable=False)

    if not _index_exists(inspector):
        op.create_index(
            _INDEX,
            _TABLE,
            ["user_id", "scan_type"],
            unique=True,
            sqlite_where=sa.text(_WHERE),
            postgresql_where=sa.text(_WHERE),
        )


def downgrade() -> None:
    """Downgrade schema."""
    inspector = sa.inspect(op.get_bind())
    if _TABLE in inspector.get_table_names() and _index_exists(inspector):
        op.drop_index(_INDEX, table_name=_TABLE)
