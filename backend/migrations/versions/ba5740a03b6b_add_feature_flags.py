"""Add feature_flags (platform flags: admin overrides of registered flags)

Creates feature_flags, identical to the FeatureFlag model in
models/db_models.py.

Idempotent: the table is created only if it does not exist (the initial
revision runs Base.metadata.create_all, so fresh databases already have it),
and downgrade drops it only if present.

Revision ID: ba5740a03b6b
Revises: ea2f610ceb51
Create Date: 2026-10-19
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "ba5740a03b6b"
down_revision: Union[str, Sequence[str], None] = "ea2f610ceb51"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    conn = op.get_bind()
    if "feature_flags" not in set(sa.inspect(conn).get_table_names()):
        op.create_table(
            "feature_flags",
            sa.Column("key", sa.String(length=64), nullable=False),
            sa.Column("enabled", sa.Boolean(), server_default="0", nullable=False),
            sa.Column("updated_by", sa.Integer(), nullable=True),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.PrimaryKeyConstraint("key"),
        )


def downgrade() -> None:
    """Downgrade schema."""
    conn = op.get_bind()
    if "feature_flags" in set(sa.inspect(conn).get_table_names()):
        op.drop_table("feature_flags")
