"""Habit cluster schema: notification prefs, delivery log, stock_events, added_price

upgrade (each step skipped when already present, checked via the inspector):
- user_preferences: push_categories, quiet_enabled, quiet_start_min,
  quiet_end_min, quiet_days, time_zone, brief_time_min, event_scope, with the
  CHECKs ck_user_preferences_quiet_start / _quiet_end / _brief_time /
  _event_scope;
- in_app_notifications: category, channel, status, dedupe_key, error,
  attempts, sent_at, opened_at, the CHECK ck_in_app_notifications_status, the
  unique index uq_in_app_notifications_dedupe_key (NULLs may repeat) and the
  index ix_in_app_notifications_user_created;
- portfolio: added_price NUMERIC(14,4) NULL with CHECK
  ck_portfolio_added_price_positive;
- creates stock_events (public NSE filings, no user data).
Existing rows take the server defaults, which satisfy every CHECK.

downgrade: drops only what this revision added and is present. CHECKs are
dropped explicitly before their columns: Alembic cannot parse CHECK
expressions, so a SQLite batch rebuild would otherwise keep a CHECK naming a
dropped column.

Revision ID: c4e81f2a9b07
Revises: ea2f610ceb51
Create Date: 2026-10-19
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "c4e81f2a9b07"
down_revision: Union[str, Sequence[str], None] = "ea2f610ceb51"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_PREFS = "user_preferences"
_NOTIF = "in_app_notifications"
_PORTFOLIO = "portfolio"
_EVENTS = "stock_events"
_NOTIF_DEDUPE_UQ = "uq_in_app_notifications_dedupe_key"
_NOTIF_USER_CREATED_IX = "ix_in_app_notifications_user_created"

_STATUS_SQL = (
    "status IN ('pending','sent','inbox_only','suppressed_pref','suppressed_quiet',"
    "'capped','failed','delivered')"
)


def _prefs_columns() -> list:
    return [
        sa.Column("push_categories", sa.JSON(), nullable=True),
        sa.Column("quiet_enabled", sa.Boolean(), nullable=False, server_default="1"),
        sa.Column("quiet_start_min", sa.Integer(), nullable=False, server_default="1320"),
        sa.Column("quiet_end_min", sa.Integer(), nullable=False, server_default="420"),
        sa.Column("quiet_days", sa.JSON(), nullable=True),
        sa.Column("time_zone", sa.String(40), nullable=False, server_default="Asia/Kolkata"),
        sa.Column("brief_time_min", sa.Integer(), nullable=False, server_default="510"),
        sa.Column("event_scope", sa.String(24), nullable=False, server_default="holdings"),
    ]


def _notif_columns() -> list:
    return [
        sa.Column("category", sa.String(32), nullable=True),
        sa.Column("channel", sa.String(16), nullable=False, server_default="inbox"),
        sa.Column("status", sa.String(20), nullable=False, server_default="delivered"),
        sa.Column("dedupe_key", sa.String(120), nullable=True),
        sa.Column("error", sa.String(64), nullable=True),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("sent_at", sa.DateTime(), nullable=True),
        sa.Column("opened_at", sa.DateTime(), nullable=True),
    ]


def _portfolio_columns() -> list:
    return [sa.Column("added_price", sa.Numeric(14, 4), nullable=True)]


# table -> (columns factory, {check name: check SQL})
_TABLES = {
    _PREFS: (
        _prefs_columns,
        {
            "ck_user_preferences_quiet_start": "quiet_start_min >= 0 AND quiet_start_min < 1440",
            "ck_user_preferences_quiet_end": "quiet_end_min >= 0 AND quiet_end_min < 1440",
            "ck_user_preferences_brief_time": "brief_time_min >= 360 AND brief_time_min <= 645",
            "ck_user_preferences_event_scope": "event_scope IN ('holdings','holdings_and_watchlist')",
        },
    ),
    _NOTIF: (_notif_columns, {"ck_in_app_notifications_status": _STATUS_SQL}),
    _PORTFOLIO: (
        _portfolio_columns,
        {"ck_portfolio_added_price_positive": "added_price IS NULL OR added_price > 0"},
    ),
}


def _columns(inspector, table: str) -> set:
    return {c["name"] for c in inspector.get_columns(table)}


def _indexes(inspector, table: str) -> set:
    return {ix.get("name") for ix in inspector.get_indexes(table)}


def _checks(inspector, table: str) -> set:
    return {c.get("name") for c in inspector.get_check_constraints(table)}


def _create_stock_events() -> None:
    # Literal name: test_base_revision_creates_current_model_tables reads it from the AST.
    op.create_table(
        "stock_events",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("symbol", sa.String(30), nullable=False),
        sa.Column("event_type", sa.String(24), nullable=False),
        sa.Column("severity", sa.String(8), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("company_name", sa.String(200), nullable=True),
        sa.Column("source", sa.String(24), nullable=False, server_default="nse_rss"),
        sa.Column("source_feed", sa.String(40), nullable=False),
        sa.Column("source_url", sa.String(500), nullable=False),
        sa.Column("event_date", sa.Date(), nullable=True),
        sa.Column("published_at", sa.DateTime(), nullable=False),
        sa.Column("dedupe_key", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("dedupe_key", name="uq_stock_events_dedupe_key"),
        sa.CheckConstraint("event_type IN ('board_meeting','kmp_exit','pledge')", name="ck_stock_events_type"),
        sa.CheckConstraint("severity IN ('high','medium','low')", name="ck_stock_events_severity"),
    )
    op.create_index("ix_stock_events_symbol_published", _EVENTS, ["symbol", "published_at"], unique=False)
    op.create_index("ix_stock_events_event_date", _EVENTS, ["event_date"], unique=False)


def upgrade() -> None:
    """Upgrade schema."""
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    tables = set(inspector.get_table_names())

    for table, (columns_factory, checks) in _TABLES.items():
        if table not in tables:
            continue
        existing_columns = _columns(inspector, table)
        existing_checks = _checks(inspector, table)
        new_columns = [c for c in columns_factory() if c.name not in existing_columns]
        new_checks = {n: sql for n, sql in checks.items() if n not in existing_checks}
        if not new_columns and not new_checks:
            continue
        with op.batch_alter_table(table, schema=None) as batch_op:
            for column in new_columns:
                batch_op.add_column(column)
            for name, sql in new_checks.items():
                batch_op.create_check_constraint(name, sql)

    if _NOTIF in tables:
        indexes = _indexes(sa.inspect(conn), _NOTIF)
        if _NOTIF_DEDUPE_UQ not in indexes:
            op.create_index(_NOTIF_DEDUPE_UQ, _NOTIF, ["dedupe_key"], unique=True)
        if _NOTIF_USER_CREATED_IX not in indexes:
            op.create_index(_NOTIF_USER_CREATED_IX, _NOTIF, ["user_id", "created_at"], unique=False)

    if _EVENTS not in tables:
        _create_stock_events()


def downgrade() -> None:
    """Downgrade schema."""
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    tables = set(inspector.get_table_names())

    if _EVENTS in tables:
        events_indexes = _indexes(inspector, _EVENTS)
        for name in ("ix_stock_events_symbol_published", "ix_stock_events_event_date"):
            if name in events_indexes:
                op.drop_index(name, table_name=_EVENTS)
        op.drop_table(_EVENTS)

    if _NOTIF in tables:
        indexes = _indexes(inspector, _NOTIF)
        for name in (_NOTIF_DEDUPE_UQ, _NOTIF_USER_CREATED_IX):
            if name in indexes:
                op.drop_index(name, table_name=_NOTIF)

    for table, (columns_factory, checks) in _TABLES.items():
        if table not in tables:
            continue
        inspector = sa.inspect(conn)
        existing_checks = _checks(inspector, table)
        existing_columns = _columns(inspector, table)
        drop_checks = [n for n in checks if n in existing_checks]
        drop_columns = [c.name for c in columns_factory() if c.name in existing_columns]
        if not drop_checks and not drop_columns:
            continue
        with op.batch_alter_table(table, schema=None) as batch_op:
            for name in drop_checks:
                batch_op.drop_constraint(name, type_="check")
            for name in drop_columns:
                batch_op.drop_column(name)
