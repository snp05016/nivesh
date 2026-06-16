"""Add ix_analysis_jobs_ticker index and AnalysisJob user cascade support.

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-06-16

The ORM model declared Index("ix_analysis_jobs_ticker", "ticker") in __table_args__
but no migration ever created it in the live database. Fresh installs via
Base.metadata.create_all() had the index; pre-existing DBs did not.
"""

from typing import Sequence, Union

from alembic import op
from sqlalchemy import inspect


revision: str = "b2c3d4e5f6a7"
down_revision: Union[str, Sequence[str], None] = "a1b2c3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _index_exists(index_name: str) -> bool:
    bind = op.get_bind()
    inspector = inspect(bind)
    for idx in inspector.get_indexes("analysis_jobs"):
        if idx["name"] == index_name:
            return True
    return False


def upgrade() -> None:
    if not _index_exists("ix_analysis_jobs_ticker"):
        op.create_index("ix_analysis_jobs_ticker", "analysis_jobs", ["ticker"])


def downgrade() -> None:
    if _index_exists("ix_analysis_jobs_ticker"):
        op.drop_index("ix_analysis_jobs_ticker", table_name="analysis_jobs")
