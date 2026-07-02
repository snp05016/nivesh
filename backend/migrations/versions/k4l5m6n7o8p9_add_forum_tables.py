"""Add community forum tables (boards, threads, posts, polls, votes)

Adds forum_boards, forum_threads, forum_posts, forum_polls,
forum_poll_options, forum_votes so the Community Forum backend
(services/forum_service.py, routers/forum.py) can serve message boards,
per-stock discussion, replies, and polls.

Revision ID: k4l5m6n7o8p9
Revises: j3k4l5m6n7o8
Create Date: 2026-07-02
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "k4l5m6n7o8p9"
down_revision: Union[str, Sequence[str], None] = "j3k4l5m6n7o8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_tables = set(inspector.get_table_names())

    if "forum_boards" not in existing_tables:
        op.create_table(
            "forum_boards",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("slug", sa.String(length=60), nullable=False),
            sa.Column("name", sa.String(length=150), nullable=False),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("board_type", sa.String(length=20), nullable=False, server_default="general"),
            sa.Column("ticker", sa.String(length=30), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.PrimaryKeyConstraint("id"),
        )
        with op.batch_alter_table("forum_boards", schema=None) as batch_op:
            batch_op.create_index(batch_op.f("ix_forum_boards_id"), ["id"], unique=False)
            batch_op.create_index(batch_op.f("ix_forum_boards_slug"), ["slug"], unique=True)
            batch_op.create_index(batch_op.f("ix_forum_boards_ticker"), ["ticker"], unique=False)

    if "forum_threads" not in existing_tables:
        op.create_table(
            "forum_threads",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("board_id", sa.Integer(), nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("title", sa.String(length=200), nullable=False),
            sa.Column("is_pinned", sa.Boolean(), nullable=False, server_default="0"),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.Column("updated_at", sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(["board_id"], ["forum_boards.id"]),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
        with op.batch_alter_table("forum_threads", schema=None) as batch_op:
            batch_op.create_index(batch_op.f("ix_forum_threads_id"), ["id"], unique=False)
            batch_op.create_index(batch_op.f("ix_forum_threads_board_id"), ["board_id"], unique=False)
            batch_op.create_index(batch_op.f("ix_forum_threads_user_id"), ["user_id"], unique=False)

    if "forum_posts" not in existing_tables:
        op.create_table(
            "forum_posts",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("thread_id", sa.Integer(), nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("parent_post_id", sa.Integer(), nullable=True),
            sa.Column("body", sa.Text(), nullable=False),
            sa.Column("is_op", sa.Boolean(), nullable=False, server_default="0"),
            sa.Column("upvotes", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("downvotes", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("moderation_action", sa.String(length=10), nullable=False, server_default="allow"),
            sa.Column("spam_score", sa.Integer(), nullable=True),
            sa.Column("sentiment", sa.String(length=10), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(["thread_id"], ["forum_threads.id"]),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
            sa.ForeignKeyConstraint(["parent_post_id"], ["forum_posts.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
        with op.batch_alter_table("forum_posts", schema=None) as batch_op:
            batch_op.create_index(batch_op.f("ix_forum_posts_id"), ["id"], unique=False)
            batch_op.create_index(batch_op.f("ix_forum_posts_thread_id"), ["thread_id"], unique=False)
            batch_op.create_index(batch_op.f("ix_forum_posts_user_id"), ["user_id"], unique=False)
            batch_op.create_index(batch_op.f("ix_forum_posts_parent_post_id"), ["parent_post_id"], unique=False)

    if "forum_polls" not in existing_tables:
        op.create_table(
            "forum_polls",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("thread_id", sa.Integer(), nullable=False),
            sa.Column("question", sa.String(length=300), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(["thread_id"], ["forum_threads.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
        with op.batch_alter_table("forum_polls", schema=None) as batch_op:
            batch_op.create_index(batch_op.f("ix_forum_polls_id"), ["id"], unique=False)
            batch_op.create_index(batch_op.f("ix_forum_polls_thread_id"), ["thread_id"], unique=True)

    if "forum_poll_options" not in existing_tables:
        op.create_table(
            "forum_poll_options",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("poll_id", sa.Integer(), nullable=False),
            sa.Column("option_text", sa.String(length=150), nullable=False),
            sa.Column("vote_count", sa.Integer(), nullable=False, server_default="0"),
            sa.ForeignKeyConstraint(["poll_id"], ["forum_polls.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
        with op.batch_alter_table("forum_poll_options", schema=None) as batch_op:
            batch_op.create_index(batch_op.f("ix_forum_poll_options_id"), ["id"], unique=False)
            batch_op.create_index(batch_op.f("ix_forum_poll_options_poll_id"), ["poll_id"], unique=False)

    if "forum_votes" not in existing_tables:
        op.create_table(
            "forum_votes",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("post_id", sa.Integer(), nullable=True),
            sa.Column("poll_id", sa.Integer(), nullable=True),
            sa.Column("poll_option_id", sa.Integer(), nullable=True),
            sa.Column("vote_value", sa.Integer(), nullable=False, server_default="1"),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
            sa.ForeignKeyConstraint(["post_id"], ["forum_posts.id"]),
            sa.ForeignKeyConstraint(["poll_id"], ["forum_polls.id"]),
            sa.ForeignKeyConstraint(["poll_option_id"], ["forum_poll_options.id"]),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("user_id", "post_id", name="uq_forum_vote_user_post"),
            sa.UniqueConstraint("user_id", "poll_id", name="uq_forum_vote_user_poll"),
        )
        with op.batch_alter_table("forum_votes", schema=None) as batch_op:
            batch_op.create_index(batch_op.f("ix_forum_votes_id"), ["id"], unique=False)
            batch_op.create_index(batch_op.f("ix_forum_votes_user_id"), ["user_id"], unique=False)
            batch_op.create_index(batch_op.f("ix_forum_votes_post_id"), ["post_id"], unique=False)
            batch_op.create_index(batch_op.f("ix_forum_votes_poll_id"), ["poll_id"], unique=False)
            batch_op.create_index(batch_op.f("ix_forum_votes_poll_option_id"), ["poll_option_id"], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_tables = set(inspector.get_table_names())

    if "forum_votes" in existing_tables:
        with op.batch_alter_table("forum_votes", schema=None) as batch_op:
            batch_op.drop_index(batch_op.f("ix_forum_votes_poll_option_id"))
            batch_op.drop_index(batch_op.f("ix_forum_votes_poll_id"))
            batch_op.drop_index(batch_op.f("ix_forum_votes_post_id"))
            batch_op.drop_index(batch_op.f("ix_forum_votes_user_id"))
            batch_op.drop_index(batch_op.f("ix_forum_votes_id"))
        op.drop_table("forum_votes")

    if "forum_poll_options" in existing_tables:
        with op.batch_alter_table("forum_poll_options", schema=None) as batch_op:
            batch_op.drop_index(batch_op.f("ix_forum_poll_options_poll_id"))
            batch_op.drop_index(batch_op.f("ix_forum_poll_options_id"))
        op.drop_table("forum_poll_options")

    if "forum_polls" in existing_tables:
        with op.batch_alter_table("forum_polls", schema=None) as batch_op:
            batch_op.drop_index(batch_op.f("ix_forum_polls_thread_id"))
            batch_op.drop_index(batch_op.f("ix_forum_polls_id"))
        op.drop_table("forum_polls")

    if "forum_posts" in existing_tables:
        with op.batch_alter_table("forum_posts", schema=None) as batch_op:
            batch_op.drop_index(batch_op.f("ix_forum_posts_parent_post_id"))
            batch_op.drop_index(batch_op.f("ix_forum_posts_user_id"))
            batch_op.drop_index(batch_op.f("ix_forum_posts_thread_id"))
            batch_op.drop_index(batch_op.f("ix_forum_posts_id"))
        op.drop_table("forum_posts")

    if "forum_threads" in existing_tables:
        with op.batch_alter_table("forum_threads", schema=None) as batch_op:
            batch_op.drop_index(batch_op.f("ix_forum_threads_user_id"))
            batch_op.drop_index(batch_op.f("ix_forum_threads_board_id"))
            batch_op.drop_index(batch_op.f("ix_forum_threads_id"))
        op.drop_table("forum_threads")

    if "forum_boards" in existing_tables:
        with op.batch_alter_table("forum_boards", schema=None) as batch_op:
            batch_op.drop_index(batch_op.f("ix_forum_boards_ticker"))
            batch_op.drop_index(batch_op.f("ix_forum_boards_slug"))
            batch_op.drop_index(batch_op.f("ix_forum_boards_id"))
        op.drop_table("forum_boards")
