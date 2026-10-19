"""Ledger asset class, statement import batches and journal market score (money C4)

upgrade (each step skipped when already present):
- creates import_batches (status CHECK ck_import_batches_status), the index
  ix_import_batches_user_created and the partial unique index
  uq_import_batches_user_file_committed on (user_id, file_sha256) WHERE
  status = 'committed';
- portfolio_transactions: asset_class VARCHAR(8) NOT NULL DEFAULT 'EQ' with
  CHECK ck_portfolio_transactions_asset_class, import_batch_id (FK
  fk_portfolio_transactions_import_batch -> import_batches.id ON DELETE SET
  NULL) and the index ix_portfolio_transactions_import_batch;
- portfolio: asset_class VARCHAR(8) NOT NULL DEFAULT 'EQ' with CHECK
  ck_portfolio_asset_class;
- trade_journal: market_score JSON NULL.
Existing rows become 'EQ' through the server default. Float columns are not
changed (DB-25).

downgrade: drops only what this revision added and is present. Rows written
by imports stay in the ledger (their batch link is lost).

Revision ID: ea2f610ceb51
Revises: 3b38ab41c39c
Create Date: 2026-10-19
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "ea2f610ceb51"
down_revision: Union[str, Sequence[str], None] = "3b38ab41c39c"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_BATCHES = "import_batches"
_BATCH_CREATED_IX = "ix_import_batches_user_created"
_BATCH_COMMITTED_UQ = "uq_import_batches_user_file_committed"
_TX = "portfolio_transactions"
_TX_CHECK = "ck_portfolio_transactions_asset_class"
_TX_FK = "fk_portfolio_transactions_import_batch"
_TX_IX = "ix_portfolio_transactions_import_batch"
_PORTFOLIO = "portfolio"
_PORTFOLIO_CHECK = "ck_portfolio_asset_class"
_JOURNAL = "trade_journal"
_ASSET_CLASS_SQL = "asset_class IN ('EQ','MF')"


def _asset_class_column() -> sa.Column:
    return sa.Column("asset_class", sa.String(8), nullable=False, server_default="EQ")


def _columns(inspector, table: str) -> set:
    return {c["name"] for c in inspector.get_columns(table)}


def _indexes(inspector, table: str) -> set:
    return {ix.get("name") for ix in inspector.get_indexes(table)}


def _checks(inspector, table: str) -> set:
    return {c.get("name") for c in inspector.get_check_constraints(table)}


def _foreign_keys(inspector, table: str) -> set:
    return {fk.get("name") for fk in inspector.get_foreign_keys(table)}


def _create_import_batches() -> None:
    # Literal name: test_base_revision_creates_current_model_tables reads it from the AST.
    op.create_table(
        "import_batches",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("source", sa.String(16), nullable=False, server_default="cams_kfintech"),
        sa.Column("status", sa.String(12), nullable=False),
        sa.Column("file_sha256", sa.String(64), nullable=True),
        sa.Column("cas_type", sa.String(10), nullable=True),
        sa.Column("statement_from", sa.Date(), nullable=True),
        sa.Column("statement_to", sa.Date(), nullable=True),
        sa.Column("preview_json", sa.JSON(), nullable=True),
        sa.Column("error_code", sa.String(40), nullable=True),
        sa.Column("schemes_total", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("schemes_imported", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("inserted_rows", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("skipped_rows", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("consent_notice_version", sa.String(16), nullable=True),
        sa.Column("consented_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("committed_at", sa.DateTime(), nullable=True),
        sa.CheckConstraint(
            "status IN ('parsing','previewed','committed','failed','cancelled')",
            name="ck_import_batches_status",
        ),
    )


def upgrade() -> None:
    """Upgrade schema."""
    inspector = sa.inspect(op.get_bind())
    tables = set(inspector.get_table_names())

    if _BATCHES not in tables:
        _create_import_batches()
        tables.add(_BATCHES)
        inspector = sa.inspect(op.get_bind())
    batch_indexes = _indexes(inspector, _BATCHES)
    if _BATCH_CREATED_IX not in batch_indexes:
        op.create_index(_BATCH_CREATED_IX, _BATCHES, ["user_id", "created_at"])
    if _BATCH_COMMITTED_UQ not in batch_indexes:
        op.create_index(
            _BATCH_COMMITTED_UQ,
            _BATCHES,
            ["user_id", "file_sha256"],
            unique=True,
            postgresql_where=sa.text("status = 'committed'"),
            sqlite_where=sa.text("status = 'committed'"),
        )

    if _TX in tables:
        columns = _columns(inspector, _TX)
        add_check = _TX_CHECK not in _checks(inspector, _TX)
        add_fk = _TX_FK not in _foreign_keys(inspector, _TX)
        if "asset_class" not in columns or "import_batch_id" not in columns or add_check or add_fk:
            with op.batch_alter_table(_TX, schema=None) as batch_op:
                if "asset_class" not in columns:
                    batch_op.add_column(_asset_class_column())
                if "import_batch_id" not in columns:
                    batch_op.add_column(sa.Column("import_batch_id", sa.Integer(), nullable=True))
                if add_check:
                    batch_op.create_check_constraint(_TX_CHECK, _ASSET_CLASS_SQL)
                if add_fk:
                    batch_op.create_foreign_key(
                        _TX_FK, _BATCHES, ["import_batch_id"], ["id"], ondelete="SET NULL"
                    )
        if _TX_IX not in _indexes(sa.inspect(op.get_bind()), _TX):
            op.create_index(_TX_IX, _TX, ["import_batch_id"])

    if _PORTFOLIO in tables:
        has_column = "asset_class" in _columns(inspector, _PORTFOLIO)
        add_check = _PORTFOLIO_CHECK not in _checks(inspector, _PORTFOLIO)
        if not has_column or add_check:
            with op.batch_alter_table(_PORTFOLIO, schema=None) as batch_op:
                if not has_column:
                    batch_op.add_column(_asset_class_column())
                if add_check:
                    batch_op.create_check_constraint(_PORTFOLIO_CHECK, _ASSET_CLASS_SQL)

    if _JOURNAL in tables and "market_score" not in _columns(inspector, _JOURNAL):
        with op.batch_alter_table(_JOURNAL, schema=None) as batch_op:
            batch_op.add_column(sa.Column("market_score", sa.JSON(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    inspector = sa.inspect(op.get_bind())
    tables = set(inspector.get_table_names())

    if _JOURNAL in tables and "market_score" in _columns(inspector, _JOURNAL):
        with op.batch_alter_table(_JOURNAL, schema=None) as batch_op:
            batch_op.drop_column("market_score")

    if _PORTFOLIO in tables:
        has_check = _PORTFOLIO_CHECK in _checks(inspector, _PORTFOLIO)
        has_column = "asset_class" in _columns(inspector, _PORTFOLIO)
        if has_check or has_column:
            with op.batch_alter_table(_PORTFOLIO, schema=None) as batch_op:
                if has_check:
                    batch_op.drop_constraint(_PORTFOLIO_CHECK, type_="check")
                if has_column:
                    batch_op.drop_column("asset_class")

    if _TX in tables:
        if _TX_IX in _indexes(inspector, _TX):
            op.drop_index(_TX_IX, table_name=_TX)
        inspector = sa.inspect(op.get_bind())
        has_check = _TX_CHECK in _checks(inspector, _TX)
        has_fk = _TX_FK in _foreign_keys(inspector, _TX)
        columns = _columns(inspector, _TX)
        if has_check or has_fk or {"asset_class", "import_batch_id"} & columns:
            with op.batch_alter_table(_TX, schema=None) as batch_op:
                if has_fk:
                    batch_op.drop_constraint(_TX_FK, type_="foreignkey")
                if has_check:
                    batch_op.drop_constraint(_TX_CHECK, type_="check")
                if "import_batch_id" in columns:
                    batch_op.drop_column("import_batch_id")
                if "asset_class" in columns:
                    batch_op.drop_column("asset_class")

    if _BATCHES in tables:
        indexes = _indexes(inspector, _BATCHES)
        for name in (_BATCH_COMMITTED_UQ, _BATCH_CREATED_IX):
            if name in indexes:
                op.drop_index(name, table_name=_BATCHES)
        op.drop_table(_BATCHES)
