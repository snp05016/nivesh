"""Add users.deleted_at (DB-06)

Right-to-erasure keeps the users row as a tombstone (retained audit, consent
and forum rows still reference it); deleted_at records when erase_user() ran.

upgrade: adds the nullable column unless it already exists.
downgrade: drops it if present.

Revision ID: 61bba5810e8e
Revises: 25342fdfb06f
Create Date: 2026-10-11
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "61bba5810e8e"
down_revision: Union[str, Sequence[str], None] = "25342fdfb06f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_column(inspector) -> bool:
    return any(c["name"] == "deleted_at" for c in inspector.get_columns("users"))


def upgrade() -> None:
    """Upgrade schema."""
    inspector = sa.inspect(op.get_bind())
    if "users" not in inspector.get_table_names() or _has_column(inspector):
        return
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.add_column(sa.Column("deleted_at", sa.DateTime(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    inspector = sa.inspect(op.get_bind())
    if "users" not in inspector.get_table_names() or not _has_column(inspector):
        return
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.drop_column("deleted_at")
