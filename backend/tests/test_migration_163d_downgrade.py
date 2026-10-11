"""GH-621: 163d22315728.downgrade must only drop objects that revision introduced.

Hermetic: builds a minimal schema in a temp SQLite file and runs the revision's
downgrade() through alembic Operations; no app import.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations

REVISION_FILE = (
    Path(__file__).resolve().parents[1]
    / "migrations" / "versions" / "163d22315728_add_portfoliogroup_and_transaction_.py"
)
EARLIER_OWNED_TABLES = {
    "youtube_video_summaries", "dividend_ledger", "in_app_notifications",
    "tax_reports", "user_preferences",
}


def _load_revision(path: Path):
    spec = importlib.util.spec_from_file_location(path.stem, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _build_schema(engine) -> None:
    md = sa.MetaData()
    pk = lambda: sa.Column("id", sa.Integer(), primary_key=True)  # noqa: E731
    sa.Table("users", md, pk())
    sa.Table(
        "portfolio_groups", md, pk(),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id")),
        sa.Index("ix_portfolio_groups_user_id", "user_id"),
    )
    sa.Table(
        "portfolio", md, pk(),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id")),
        sa.Column("is_virtual", sa.Boolean(), server_default="0", nullable=False),
        sa.Column("group_id", sa.Integer(), sa.ForeignKey("portfolio_groups.id")),
        sa.Index("ix_portfolio_group_id", "group_id"),
    )
    sa.Table(
        "trade_journal", md, pk(),
        sa.Column("is_virtual", sa.Boolean(), server_default="0", nullable=False),
    )
    sa.Table(
        "portfolio_transactions", md, pk(),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id")),
        sa.Column("group_id", sa.Integer(), sa.ForeignKey("portfolio_groups.id")),
        sa.Column("ticker", sa.String(30)),
        sa.Column("date", sa.DateTime()),
        sa.Index("ix_portfolio_transactions_user_id", "user_id"),
        sa.Index("ix_portfolio_transactions_ticker", "ticker"),
        sa.Index("ix_portfolio_transactions_group_id", "group_id"),
        sa.Index("ix_portfolio_transactions_date", "date"),
    )
    for name in EARLIER_OWNED_TABLES:
        sa.Table(name, md, pk(), sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id")))
    md.create_all(engine)


def test_downgrade_keeps_tables_owned_by_earlier_revisions(tmp_path):
    engine = sa.create_engine(f"sqlite:///{tmp_path / 'm163d.db'}")
    _build_schema(engine)
    revision = _load_revision(REVISION_FILE)

    with engine.begin() as conn:
        with Operations.context(MigrationContext.configure(conn)):
            revision.downgrade()

    insp = sa.inspect(engine)
    tables = set(insp.get_table_names())
    assert EARLIER_OWNED_TABLES <= tables, f"dropped earlier-owned tables: {EARLIER_OWNED_TABLES - tables}"
    assert "portfolio_transactions" not in tables
    assert "portfolio_groups" not in tables

    portfolio_cols = {c["name"] for c in insp.get_columns("portfolio")}
    assert "is_virtual" in portfolio_cols, "portfolio.is_virtual belongs to g1h2i3j4k5l6"
    assert "group_id" not in portfolio_cols
    assert "is_virtual" not in {c["name"] for c in insp.get_columns("trade_journal")}
    engine.dispose()
