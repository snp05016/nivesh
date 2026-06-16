"""fix calibrated_confidence nullable=False

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-06-16

Migration a1b2c3d4e5f6 added calibrated_confidence with nullable=True but the
ORM declares nullable=False. This migration corrects the column definition.
All existing rows already have a server_default of 0.0 so no NULL values exist.
"""
from alembic import op
import sqlalchemy as sa

revision = "c3d4e5f6a7b8"
down_revision = "b2c3d4e5f6a7"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("analysis_history", schema=None) as batch_op:
        batch_op.alter_column(
            "calibrated_confidence",
            existing_type=sa.Float(),
            nullable=False,
            server_default="0.0",
        )


def downgrade():
    with op.batch_alter_table("analysis_history", schema=None) as batch_op:
        batch_op.alter_column(
            "calibrated_confidence",
            existing_type=sa.Float(),
            nullable=True,
            server_default="0.0",
        )
