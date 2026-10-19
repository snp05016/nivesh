"""Add job_runs (per-run scheduler history); drop scheduler_job_status

Creates job_runs and its two indexes, identical to the JobRun model in
models/db_models.py. job_runs replaces the one-row-per-job
scheduler_job_status table (SILENT-13), which upgrade drops if present and
downgrade recreates empty.

Idempotent: every step is skipped when already done.

Revision ID: 24a2a72cebb6
Revises: ba5740a03b6b
Create Date: 2026-10-19
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "24a2a72cebb6"
down_revision: Union[str, Sequence[str], None] = "ba5740a03b6b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    conn = op.get_bind()
    tables = set(sa.inspect(conn).get_table_names())

    if "job_runs" not in tables:
        op.create_table(
            "job_runs",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("job_name", sa.String(length=64), nullable=False),
            sa.Column("status", sa.String(length=16), nullable=False),
            sa.Column("started_at", sa.DateTime(), nullable=False),
            sa.Column("finished_at", sa.DateTime(), nullable=True),
            sa.Column("duration_ms", sa.Integer(), nullable=True),
            sa.Column("rows_written", sa.Integer(), nullable=True),
            sa.Column("error", sa.Text(), nullable=True),
            sa.Column("meta", sa.JSON(none_as_null=True), nullable=True),
            sa.PrimaryKeyConstraint("id"),
            sa.CheckConstraint("status IN ('running','ok','failed')", name="ck_job_runs_status"),
        )
    existing = {i["name"] for i in sa.inspect(conn).get_indexes("job_runs")}
    if "ix_job_runs_job_started" not in existing:
        op.create_index("ix_job_runs_job_started", "job_runs", ["job_name", "started_at"], unique=False)
    if "ix_job_runs_status_started" not in existing:
        op.create_index("ix_job_runs_status_started", "job_runs", ["status", "started_at"], unique=False)

    if "scheduler_job_status" in tables:
        op.drop_table("scheduler_job_status")


def downgrade() -> None:
    """Downgrade schema."""
    conn = op.get_bind()
    tables = set(sa.inspect(conn).get_table_names())

    if "scheduler_job_status" not in tables:
        op.create_table(
            "scheduler_job_status",
            sa.Column("job_name", sa.String(length=64), nullable=False),
            sa.Column("status", sa.String(length=16), nullable=False),
            sa.Column("last_started_at", sa.DateTime(), nullable=True),
            sa.Column("last_finished_at", sa.DateTime(), nullable=True),
            sa.Column("last_error", sa.Text(), nullable=True),
            sa.Column("last_result_json", sa.Text(), nullable=True),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.PrimaryKeyConstraint("job_name"),
        )
    if "job_runs" in tables:
        op.drop_table("job_runs")
