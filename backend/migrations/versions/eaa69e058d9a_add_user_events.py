"""Add user_events (consented first-party usage events, I47)

Creates user_events with its two indexes, identical to the UserEvent model in
models/db_models.py. Idempotent: the table and each index are created only when
missing; downgrade drops the table only when present.

Revision ID: eaa69e058d9a
Revises: 24a2a72cebb6
Create Date: 2026-10-19
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "eaa69e058d9a"
down_revision: Union[str, Sequence[str], None] = "24a2a72cebb6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    conn = op.get_bind()
    if "user_events" not in set(sa.inspect(conn).get_table_names()):
        op.create_table(
            "user_events",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("event_name", sa.String(length=40), nullable=False),
            sa.Column("props", sa.JSON(none_as_null=True), nullable=True),
            sa.Column("app_version", sa.String(length=20), nullable=True),
            sa.Column("platform", sa.String(length=10), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
    existing = {i["name"] for i in sa.inspect(conn).get_indexes("user_events")}
    if "ix_user_events_name_created" not in existing:
        op.create_index("ix_user_events_name_created", "user_events", ["event_name", "created_at"], unique=False)
    if "ix_user_events_user_created" not in existing:
        op.create_index("ix_user_events_user_created", "user_events", ["user_id", "created_at"], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    conn = op.get_bind()
    if "user_events" in set(sa.inspect(conn).get_table_names()):
        op.drop_table("user_events")
