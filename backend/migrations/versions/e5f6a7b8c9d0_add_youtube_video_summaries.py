"""Add youtube_video_summaries table

Revision ID: e5f6a7b8c9d0
Revises: 842e8701256b
Create Date: 2026-06-26 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "e5f6a7b8c9d0"
down_revision: Union[str, Sequence[str], None] = "842e8701256b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create youtube_video_summaries table."""
    op.create_table(
        "youtube_video_summaries",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("video_id", sa.String(length=20), nullable=False),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("title", sa.Text(), nullable=True, server_default=""),
        sa.Column("channel", sa.Text(), nullable=True, server_default=""),
        sa.Column("duration_seconds", sa.Integer(), nullable=True, server_default="0"),
        sa.Column("transcript_hash", sa.String(length=64), nullable=True, server_default=""),
        sa.Column("transcript_source", sa.String(length=50), nullable=True, server_default=""),
        sa.Column("summary_provider", sa.String(length=50), nullable=True, server_default=""),
        sa.Column("summary_json", sa.Text(), nullable=True, server_default="{}"),
        sa.Column("timestamps_json", sa.Text(), nullable=True, server_default="[]"),
        sa.Column("raw_transcript_preview", sa.Text(), nullable=True, server_default=""),
        sa.Column("estimated_input_tokens", sa.Integer(), nullable=True, server_default="0"),
        sa.Column("estimated_output_tokens", sa.Integer(), nullable=True, server_default="0"),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.Column("last_accessed_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("video_id"),
    )
    with op.batch_alter_table("youtube_video_summaries", schema=None) as batch_op:
        batch_op.create_index("ix_youtube_video_summaries_id", ["id"], unique=False)
        batch_op.create_index("ix_youtube_video_summaries_video_id", ["video_id"], unique=True)


def downgrade() -> None:
    """Drop youtube_video_summaries table."""
    with op.batch_alter_table("youtube_video_summaries", schema=None) as batch_op:
        batch_op.drop_index("ix_youtube_video_summaries_video_id")
        batch_op.drop_index("ix_youtube_video_summaries_id")

    op.drop_table("youtube_video_summaries")
