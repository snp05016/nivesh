"""Purge mock earnings surprise rows (FAKE-11)

The old Earnings Surprise service persisted demo rows under the constant
quarter label 'Q4 FY24' with a fabricated price reaction and mock score.
Every row it ever wrote carries that label, so they are deleted here.

upgrade: skipped if the table is missing.
downgrade: no-op (synthetic rows are not restored).

Revision ID: 25342fdfb06f
Revises: 4aa54575a6f3
Create Date: 2026-10-11
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "25342fdfb06f"
down_revision: Union[str, Sequence[str], None] = "4aa54575a6f3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TABLE = "earnings_surprise_history"


def upgrade() -> None:
    """Upgrade schema."""
    conn = op.get_bind()
    if _TABLE not in sa.inspect(conn).get_table_names():
        return
    conn.execute(sa.text(f"DELETE FROM {_TABLE} WHERE quarter = 'Q4 FY24'"))


def downgrade() -> None:
    """Downgrade schema."""
