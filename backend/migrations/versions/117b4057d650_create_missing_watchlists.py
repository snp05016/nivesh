"""Create watchlists table on databases that never got it

1f1bb7a084e5 (add_watchlist_and_userpreferences) is a no-op, so databases
built before the Watchlist model existed and then upgraded (instead of
create_all'd) have no watchlists table (DB-07). Fresh databases already get it
from the frozen baseline, hence the existence guard.

Revision ID: 117b4057d650
Revises: ec35eaf96b81
Create Date: 2026-10-11
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "117b4057d650"
down_revision: Union[str, Sequence[str], None] = "ec35eaf96b81"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    existing_tables = set(sa.inspect(op.get_bind()).get_table_names())
    if "watchlists" in existing_tables:
        return

    op.create_table(
        "watchlists",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("ticker", sa.String(30), nullable=False),
        sa.Column("added_at", sa.DateTime()),
    )
    op.create_index("ix_watchlists_id", "watchlists", ["id"], unique=False)
    op.create_index("ix_watchlists_user_id", "watchlists", ["user_id"], unique=False)
    op.create_index("ix_watchlists_ticker", "watchlists", ["ticker"], unique=False)


def downgrade() -> None:
    """Downgrade schema.

    No-op: on fresh databases the frozen baseline owns watchlists, and this
    revision cannot tell whether it created the table, so dropping it here
    could delete user watchlists that predate it.
    """
