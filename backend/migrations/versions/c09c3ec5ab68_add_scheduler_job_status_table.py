"""Add scheduler_job_status table (SILENT-13)

One row per scheduled job (last status, start/finish time, last error, last result),
identical to the SchedulerJobStatus model in models/db_models.py. The scheduler
worker writes it; the admin dashboard on any worker reads it.

Idempotent: the table is created only if it does not exist (fresh databases get it
from Base.metadata.create_all), and downgrade drops it only if it exists.

Revision ID: c09c3ec5ab68
Revises: a8fd0770d4d1
Create Date: 2026-10-11
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "c09c3ec5ab68"
down_revision: Union[str, Sequence[str], None] = "a8fd0770d4d1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    conn = op.get_bind()
    if "scheduler_job_status" in set(sa.inspect(conn).get_table_names()):
        return
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


def downgrade() -> None:
    """Downgrade schema."""
    conn = op.get_bind()
    if "scheduler_job_status" in set(sa.inspect(conn).get_table_names()):
        op.drop_table("scheduler_job_status")
