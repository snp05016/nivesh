"""Data foundation: instruments, aliases, daily_prices, corporate-action applications, results digests

upgrade (each step skipped when already present):
- creates instruments, instrument_aliases, daily_prices,
  corporate_action_applications (with the coalesce(group_id, 0) unique
  expression index) and results_digests;
- mutual_funds: scheme_type, is_active, track_nav, nav_source and
  ix_mutual_funds_listing;
- corporate_actions: action_type, ex_on, ratio, source, nse_confirmed,
  updated_at and the unique index uq_corporate_actions_ticker_type_ex.
No seed rows.

downgrade: drops only what this revision added and is present, tables first.

Revision ID: ecac0bc9105a
Revises: ea2f610ceb51
Create Date: 2026-10-19
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "ecac0bc9105a"
down_revision: Union[str, Sequence[str], None] = "ea2f610ceb51"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_MF = "mutual_funds"
_MF_IX = "ix_mutual_funds_listing"
_CA = "corporate_actions"
_CA_UQ = "uq_corporate_actions_ticker_type_ex"


def _columns(inspector, table: str) -> set:
    return {c["name"] for c in inspector.get_columns(table)}


def _indexes(inspector, table: str) -> set:
    return {ix.get("name") for ix in inspector.get_indexes(table)}


def _create_instruments() -> None:
    op.create_table(
        "instruments",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("asset_class", sa.String(8), nullable=False),
        sa.Column("symbol", sa.String(30), nullable=True),
        sa.Column("isin", sa.String(12), nullable=True),
        sa.Column("isin_alt", sa.String(12), nullable=True),
        sa.Column("amfi_scheme_code", sa.String(20), nullable=True),
        sa.Column("entity_id", sa.String(24), nullable=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("series", sa.String(4), nullable=True),
        sa.Column("listing_date", sa.Date(), nullable=True),
        sa.Column("status", sa.String(10), nullable=False, server_default="active"),
        sa.Column("source", sa.String(16), nullable=False),
        sa.Column("last_seen_on", sa.Date(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.CheckConstraint("asset_class IN ('EQ','MF','INDEX')", name="ck_instruments_asset_class"),
        sa.CheckConstraint("status IN ('active','inactive')", name="ck_instruments_status"),
        sa.UniqueConstraint("asset_class", "symbol", name="uq_instruments_class_symbol"),
        sa.UniqueConstraint("amfi_scheme_code", name="uq_instruments_amfi_code"),
        sa.UniqueConstraint("entity_id", name="uq_instruments_entity_id"),
    )


def _create_instrument_aliases() -> None:
    op.create_table(
        "instrument_aliases",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("instrument_id", sa.Integer(), sa.ForeignKey("instruments.id", ondelete="CASCADE"), nullable=False),
        sa.Column("kind", sa.String(8), nullable=False),
        sa.Column("value", sa.String(30), nullable=False),
        sa.Column("valid_to", sa.Date(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.CheckConstraint("kind IN ('isin','symbol')", name="ck_instrument_aliases_kind"),
        sa.UniqueConstraint("kind", "value", "instrument_id", name="uq_instrument_aliases_kind_value"),
    )


def _create_daily_prices() -> None:
    op.create_table(
        "daily_prices",
        sa.Column("instrument_id", sa.Integer(), sa.ForeignKey("instruments.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("trade_date", sa.Date(), primary_key=True),
        sa.Column("open", sa.Numeric(14, 4), nullable=True),
        sa.Column("high", sa.Numeric(14, 4), nullable=True),
        sa.Column("low", sa.Numeric(14, 4), nullable=True),
        sa.Column("close", sa.Numeric(14, 4), nullable=False),
        sa.Column("prev_close", sa.Numeric(14, 4), nullable=True),
        sa.Column("volume", sa.BigInteger(), nullable=True),
        sa.Column("turnover_inr", sa.Numeric(20, 2), nullable=True),
        sa.Column("trades", sa.Integer(), nullable=True),
        sa.Column("source", sa.String(16), nullable=False),
        sa.Column("event", sa.String(16), nullable=True),
        sa.Column("quality_flags", sa.String(40), nullable=True),
        sa.Column("ingested_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint("source IN ('nse_bhavcopy','amfi','yfinance')", name="ck_daily_prices_source"),
        sa.CheckConstraint("close > 0", name="ck_daily_prices_close_positive"),
    )


def _create_ca_applications() -> None:
    op.create_table(
        "corporate_action_applications",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("group_id", sa.Integer(), sa.ForeignKey("portfolio_groups.id", ondelete="CASCADE"), nullable=True),
        sa.Column("corporate_action_id", sa.Integer(), sa.ForeignKey("corporate_actions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("status", sa.String(12), nullable=False, server_default="pending"),
        sa.Column("shares_before", sa.Numeric(18, 6), nullable=True),
        sa.Column("transaction_id", sa.Integer(), nullable=True),
        sa.Column("decided_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint("status IN ('pending','applied','dismissed')", name="ck_ca_applications_status"),
    )


def _create_results_digests() -> None:
    op.create_table(
        "results_digests",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("symbol", sa.String(30), nullable=False),
        sa.Column("period_end", sa.Date(), nullable=False),
        sa.Column("filing_url", sa.String(500), nullable=True),
        sa.Column("filing_title", sa.String(300), nullable=True),
        sa.Column("announced_at", sa.DateTime(), nullable=True),
        sa.Column("revenue_inr", sa.Numeric(20, 2), nullable=True),
        sa.Column("net_profit_inr", sa.Numeric(20, 2), nullable=True),
        sa.Column("eps", sa.Numeric(12, 2), nullable=True),
        sa.Column("revenue_yoy_pct", sa.Float(), nullable=True),
        sa.Column("net_profit_yoy_pct", sa.Float(), nullable=True),
        sa.Column("eps_yoy_pct", sa.Float(), nullable=True),
        sa.Column("numbers_source", sa.String(24), nullable=True),
        sa.Column("numbers_status", sa.String(12), nullable=False, server_default="pending"),
        sa.Column("numbers_fetched_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.CheckConstraint("numbers_status IN ('pending','ok','unavailable')", name="ck_results_digests_status"),
        sa.UniqueConstraint("symbol", "period_end", name="uq_results_digests_symbol_period"),
    )


def _ensure_index(table: str, name: str, columns: list, unique: bool = False) -> None:
    if name not in _indexes(sa.inspect(op.get_bind()), table):
        op.create_index(name, table, columns, unique=unique)


def upgrade() -> None:
    """Upgrade schema."""
    tables = set(sa.inspect(op.get_bind()).get_table_names())

    if "instruments" not in tables:
        _create_instruments()
    _ensure_index("instruments", "ix_instruments_isin", ["isin"])
    _ensure_index("instruments", "ix_instruments_isin_alt", ["isin_alt"])

    if "instrument_aliases" not in tables:
        _create_instrument_aliases()
    _ensure_index("instrument_aliases", "ix_instrument_aliases_lookup", ["kind", "value"])

    if "daily_prices" not in tables:
        _create_daily_prices()
    _ensure_index("daily_prices", "ix_daily_prices_trade_date", ["trade_date"])

    if "corporate_action_applications" not in tables:
        _create_ca_applications()
    # Expression index: SQLite cannot reflect it, so the inspector check in _ensure_index would miss it.
    op.create_index(
        "uq_ca_applications_user_action_group",
        "corporate_action_applications",
        ["user_id", "corporate_action_id", sa.text("coalesce(group_id, 0)")],
        unique=True,
        if_not_exists=True,
    )
    _ensure_index("corporate_action_applications", "ix_ca_applications_user_status", ["user_id", "status"])

    if "results_digests" not in tables:
        _create_results_digests()

    inspector = sa.inspect(op.get_bind())
    if _MF in tables:
        columns = _columns(inspector, _MF)
        wanted = [
            ("scheme_type", sa.Column("scheme_type", sa.String(16), nullable=True)),
            ("is_active", sa.Column("is_active", sa.Boolean(), nullable=False, server_default="1")),
            ("track_nav", sa.Column("track_nav", sa.Boolean(), nullable=False, server_default="0")),
            ("nav_source", sa.Column("nav_source", sa.String(16), nullable=True)),
        ]
        missing = [col for name, col in wanted if name not in columns]
        if missing:
            with op.batch_alter_table(_MF, schema=None) as batch_op:
                for col in missing:
                    batch_op.add_column(col)
        _ensure_index(_MF, _MF_IX, ["is_active", "scheme_type", "is_direct_plan", "is_growth_plan"])

    if _CA in tables:
        columns = _columns(inspector, _CA)
        wanted = [
            ("action_type", sa.Column("action_type", sa.String(16), nullable=True)),
            ("ex_on", sa.Column("ex_on", sa.Date(), nullable=True)),
            ("ratio", sa.Column("ratio", sa.Numeric(12, 6), nullable=True)),
            ("source", sa.Column("source", sa.String(16), nullable=True)),
            ("nse_confirmed", sa.Column("nse_confirmed", sa.Boolean(), nullable=True)),
            ("updated_at", sa.Column("updated_at", sa.DateTime(), nullable=True)),
        ]
        missing = [col for name, col in wanted if name not in columns]
        if missing:
            with op.batch_alter_table(_CA, schema=None) as batch_op:
                for col in missing:
                    batch_op.add_column(col)
        _ensure_index(_CA, _CA_UQ, ["ticker", "action_type", "ex_on"], unique=True)


def downgrade() -> None:
    """Downgrade schema."""
    inspector = sa.inspect(op.get_bind())
    tables = set(inspector.get_table_names())

    for table in ("corporate_action_applications", "daily_prices", "instrument_aliases",
                  "results_digests", "instruments"):
        if table in tables:
            op.drop_table(table)  # drops the table's own indexes

    if _CA in tables:
        if _CA_UQ in _indexes(inspector, _CA):
            op.drop_index(_CA_UQ, table_name=_CA)
        drop = [c for c in ("action_type", "ex_on", "ratio", "source", "nse_confirmed", "updated_at")
                if c in _columns(inspector, _CA)]
        if drop:
            with op.batch_alter_table(_CA, schema=None) as batch_op:
                for name in drop:
                    batch_op.drop_column(name)

    if _MF in tables:
        if _MF_IX in _indexes(inspector, _MF):
            op.drop_index(_MF_IX, table_name=_MF)
        drop = [c for c in ("scheme_type", "is_active", "track_nav", "nav_source")
                if c in _columns(inspector, _MF)]
        if drop:
            with op.batch_alter_table(_MF, schema=None) as batch_op:
                for name in drop:
                    batch_op.drop_column(name)
