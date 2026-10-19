"""Research Lab tables: lab_sessions, lab_experiments, lab_learner_progress

upgrade: creates each table (and its user_id index) only when it is missing,
checked via the inspector, so a DB built by create_all upgrades cleanly.
downgrade: drops only those of the three tables that are present.

Revision ID: 8f3c2a7d9e15
Revises: 5c2e9b7d41af
Create Date: 2026-10-19
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "8f3c2a7d9e15"
down_revision: Union[str, Sequence[str], None] = "5c2e9b7d41af"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_SESSIONS_IX = "ix_lab_sessions_user_id"
_EXPERIMENTS_IX = "ix_lab_experiments_user_id"


def _create_sessions() -> None:
    # Literal table names: test_base_revision_creates_current_model_tables reads them from the AST.
    op.create_table(
        "lab_sessions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(120), nullable=False),
        sa.Column("scenario_id", sa.String(64), nullable=True),
        sa.Column("config", sa.JSON(), nullable=False),
        sa.Column("actions", sa.JSON(), nullable=False),
        sa.Column("clock", sa.Date(), nullable=True),
        sa.Column("equity", sa.Numeric(14, 4), nullable=True),
        sa.Column("finished", sa.Boolean(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(_SESSIONS_IX, "lab_sessions", ["user_id"], unique=False)


def _create_experiments() -> None:
    op.create_table(
        "lab_experiments",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column("spec", sa.JSON(), nullable=False),
        sa.Column("fingerprint", sa.String(64), nullable=True),
        sa.Column("verdict", sa.String(32), nullable=False),
        sa.Column("report", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(_EXPERIMENTS_IX, "lab_experiments", ["user_id"], unique=False)


def _create_progress() -> None:
    op.create_table(
        "lab_learner_progress",
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("state", sa.JSON(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("user_id"),
    )


_TABLES = {
    "lab_sessions": (_create_sessions, _SESSIONS_IX),
    "lab_experiments": (_create_experiments, _EXPERIMENTS_IX),
    "lab_learner_progress": (_create_progress, None),
}


def upgrade() -> None:
    """Upgrade schema."""
    inspector = sa.inspect(op.get_bind())
    tables = set(inspector.get_table_names())
    for table, (create, index) in _TABLES.items():
        if table not in tables:
            create()
        elif index and index not in {ix.get("name") for ix in inspector.get_indexes(table)}:
            op.create_index(index, table, ["user_id"], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    inspector = sa.inspect(op.get_bind())
    tables = set(inspector.get_table_names())
    for table, (_create, index) in reversed(list(_TABLES.items())):
        if table not in tables:
            continue
        if index and index in {ix.get("name") for ix in inspector.get_indexes(table)}:
            op.drop_index(index, table_name=table)
        op.drop_table(table)
