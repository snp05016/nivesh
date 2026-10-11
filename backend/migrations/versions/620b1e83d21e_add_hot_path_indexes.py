"""Add hot-path indexes (PERF-15)

Indexes for the queries that run on every request or poll: the SSE job monitor
(analysis_jobs.status), the alert poller (price_targets.triggered), the home
feed (news_articles / youtube_videos published_at, youtube views) and the
analysis_history cache gate and earnings-date filters.

upgrade: each index is created only if its table exists and the index does not.
downgrade: each index is dropped only if present.

Revision ID: 620b1e83d21e
Revises: 2b3e6056a7c7
Create Date: 2026-10-11
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "620b1e83d21e"
down_revision: Union[str, Sequence[str], None] = "2b3e6056a7c7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_INDEXES = [
    ("ix_analysis_history_analysis_date",       "analysis_history", ["analysis_date"]),
    ("ix_analysis_history_ticker_scan_created", "analysis_history", ["ticker", "scan_type", "created_at"]),
    ("ix_analysis_jobs_status_created",         "analysis_jobs",    ["status", "created_at"]),
    ("ix_price_targets_triggered_ticker",       "price_targets",    ["triggered", "ticker"]),
    ("ix_news_articles_published_at",           "news_articles",    ["published_at"]),
    ("ix_youtube_videos_published_at",          "youtube_videos",   ["published_at"]),
    ("ix_youtube_videos_ticker_views",          "youtube_videos",   ["matched_ticker", "view_count"]),
]


def upgrade() -> None:
    tables = set(sa.inspect(op.get_bind()).get_table_names())
    for name, table, cols in _INDEXES:
        if table in tables:
            op.create_index(name, table, cols, unique=False, if_not_exists=True)


def downgrade() -> None:
    tables = set(sa.inspect(op.get_bind()).get_table_names())
    for name, table, _cols in reversed(_INDEXES):
        if table in tables:
            op.drop_index(name, table_name=table, if_exists=True)
