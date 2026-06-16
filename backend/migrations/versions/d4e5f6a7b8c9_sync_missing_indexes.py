"""sync missing indexes — catch-up for stamped migrations

Revision ID: d4e5f6a7b8c9
Revises: b2c3d4e5f6a7
Create Date: 2026-06-17

Migrations a1b2c3d4e5f6 and b2c3d4e5f6a7 were stamped (not run) on the
production server because the DB was originally created via create_all().
The table columns exist but the named indexes do not. This migration adds
all ORM-declared indexes idempotently using IF NOT EXISTS.
"""
from alembic import op


revision = "d4e5f6a7b8c9"
down_revision = "b2c3d4e5f6a7"
branch_labels = None
depends_on = None

_INDEXES = [
    # analysis_history
    ("ix_analysis_history_user_id",        "analysis_history",  ["user_id"],              False),
    ("ix_analysis_history_ticker",         "analysis_history",  ["ticker"],               False),
    ("ix_analysis_history_scan_type",      "analysis_history",  ["scan_type"],            False),
    ("ix_analysis_history_created_at",     "analysis_history",  ["created_at"],           False),
    ("ix_analysis_history_ticker_user",    "analysis_history",  ["ticker", "user_id"],    False),
    # analysis_jobs
    ("ix_analysis_jobs_user_id",           "analysis_jobs",     ["user_id"],              False),
    ("ix_analysis_jobs_ticker",            "analysis_jobs",     ["ticker"],               False),
    # device_tokens
    ("ix_device_tokens_user_id",           "device_tokens",     ["user_id"],              False),
    # portfolio
    ("ix_portfolio_user_id",              "portfolio",          ["user_id"],              False),
    ("ix_portfolio_user_ticker",          "portfolio",          ["user_id", "ticker"],    False),
    ("ix_portfolio_group",               "portfolio",           ["user_id", "group_name"], False),
    # price_targets
    ("ix_price_targets_user_id",          "price_targets",      ["user_id"],              False),
    # trade_journal
    ("ix_trade_journal_user_id",          "trade_journal",      ["user_id"],              False),
    # youtube_videos — rename from ix_yt_matched_ticker
    ("ix_youtube_videos_matched_ticker",  "youtube_videos",     ["matched_ticker"],       False),
]


def upgrade():
    # Drop old youtube_videos index if it exists under the old name
    with op.batch_alter_table("youtube_videos") as batch_op:
        try:
            batch_op.drop_index("ix_yt_matched_ticker")
        except Exception:
            pass  # already gone

    for name, table, cols, unique in _INDEXES:
        op.create_index(name, table, cols, unique=unique, if_not_exists=True)


def downgrade():
    for name, table, cols, unique in reversed(_INDEXES):
        op.drop_index(name, table_name=table, if_exists=True)

    op.create_index("ix_yt_matched_ticker", "youtube_videos", ["matched_ticker"],
                    unique=False, if_not_exists=True)
