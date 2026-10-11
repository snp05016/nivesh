"""Add forum_reports and user_blocks tables (forum report / block flow)

Backs the App Store 1.2 user-generated-content controls in
services/forum_service.py: users can report a forum post (ForumReport) and
block another user (UserBlock); reported/blocked content is filtered out of
that viewer's forum reads and moderators resolve reports via
/api/forum/admin/reports.

Revision ID: e3c2837fd058
Revises: t4u5v6w7x8y9
Create Date: 2026-10-11
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "e3c2837fd058"
down_revision: Union[str, Sequence[str], None] = "t4u5v6w7x8y9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    inspector = sa.inspect(op.get_bind())
    existing_tables = set(inspector.get_table_names())

    if "forum_reports" not in existing_tables:
        op.create_table(
            "forum_reports",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("reporter_user_id", sa.Integer(), nullable=False),
            sa.Column("post_id", sa.Integer(), nullable=False),
            sa.Column("reason", sa.String(length=20), nullable=False),
            sa.Column("details", sa.Text(), nullable=True),
            sa.Column("status", sa.String(length=12), nullable=False, server_default="open"),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(["reporter_user_id"], ["users.id"]),
            sa.ForeignKeyConstraint(["post_id"], ["forum_posts.id"]),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("reporter_user_id", "post_id", name="uq_forum_report_reporter_post"),
        )
        with op.batch_alter_table("forum_reports", schema=None) as batch_op:
            batch_op.create_index(batch_op.f("ix_forum_reports_id"), ["id"], unique=False)
            batch_op.create_index(batch_op.f("ix_forum_reports_reporter_user_id"), ["reporter_user_id"], unique=False)
            batch_op.create_index(batch_op.f("ix_forum_reports_post_id"), ["post_id"], unique=False)
            batch_op.create_index(batch_op.f("ix_forum_reports_status"), ["status"], unique=False)

    if "user_blocks" not in existing_tables:
        op.create_table(
            "user_blocks",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("blocker_user_id", sa.Integer(), nullable=False),
            sa.Column("blocked_user_id", sa.Integer(), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(["blocker_user_id"], ["users.id"]),
            sa.ForeignKeyConstraint(["blocked_user_id"], ["users.id"]),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("blocker_user_id", "blocked_user_id", name="uq_user_block_pair"),
        )
        with op.batch_alter_table("user_blocks", schema=None) as batch_op:
            batch_op.create_index(batch_op.f("ix_user_blocks_id"), ["id"], unique=False)
            batch_op.create_index(batch_op.f("ix_user_blocks_blocker_user_id"), ["blocker_user_id"], unique=False)
            batch_op.create_index(batch_op.f("ix_user_blocks_blocked_user_id"), ["blocked_user_id"], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    inspector = sa.inspect(op.get_bind())
    existing_tables = set(inspector.get_table_names())

    if "user_blocks" in existing_tables:
        op.drop_table("user_blocks")
    if "forum_reports" in existing_tables:
        op.drop_table("forum_reports")
