"""Add Key Fact Statement snapshot to loan_applications (FINSEC-26)

Each application stores the APR and total fees of the KFS for its own amount
and tenure, and when the applicant acknowledged that KFS.

upgrade: adds the three nullable columns that are missing.
downgrade: drops the ones that are present.

Revision ID: 3b38ab41c39c
Revises: c09c3ec5ab68
Create Date: 2026-10-11
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "3b38ab41c39c"
down_revision: Union[str, Sequence[str], None] = "c09c3ec5ab68"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TABLE = "loan_applications"


def _columns() -> list[sa.Column]:
    return [
        sa.Column("kfs_apr_pct", sa.Numeric(6, 2), nullable=True),
        sa.Column("kfs_total_fees", sa.Numeric(14, 2), nullable=True),
        sa.Column("kfs_acknowledged_at", sa.DateTime(), nullable=True),
    ]


def _existing() -> set[str] | None:
    inspector = sa.inspect(op.get_bind())
    if _TABLE not in inspector.get_table_names():
        return None
    return {c["name"] for c in inspector.get_columns(_TABLE)}


def upgrade() -> None:
    """Upgrade schema."""
    existing = _existing()
    if existing is None:
        return
    missing = [c for c in _columns() if c.name not in existing]
    if not missing:
        return
    with op.batch_alter_table(_TABLE, schema=None) as batch_op:
        for column in missing:
            batch_op.add_column(column)


def downgrade() -> None:
    """Downgrade schema."""
    existing = _existing()
    if existing is None:
        return
    present = [c.name for c in _columns() if c.name in existing]
    if not present:
        return
    with op.batch_alter_table(_TABLE, schema=None) as batch_op:
        for name in present:
            batch_op.drop_column(name)
