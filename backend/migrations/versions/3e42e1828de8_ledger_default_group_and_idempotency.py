"""One default portfolio group per user + ledger idempotency key (DB-09)

upgrade:
- demotes duplicate default groups (is_default = false for every default
  group except the lowest id per user; scripts/migrate_ledger.py used to add a
  second default "Legacy Holdings" group), then creates the partial unique
  index uq_portfolio_groups_one_default on portfolio_groups(user_id) WHERE
  is_default;
- adds portfolio_transactions.client_request_id and the unique index
  uq_portfolio_transactions_client_req on (user_id, client_request_id); NULLs
  never collide, so existing rows are unaffected.
Each step is skipped when already present.

downgrade: drops both indexes and the column if present. Demoted groups stay
demoted.

Revision ID: 3e42e1828de8
Revises: 2057be030154
Create Date: 2026-10-11
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "3e42e1828de8"
down_revision: Union[str, Sequence[str], None] = "2057be030154"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_GROUPS = "portfolio_groups"
_GROUP_INDEX = "uq_portfolio_groups_one_default"
_TX = "portfolio_transactions"
_TX_INDEX = "uq_portfolio_transactions_client_req"
_TX_COLUMN = "client_request_id"


def _index_names(inspector, table: str) -> set:
    return {ix.get("name") for ix in inspector.get_indexes(table)}


def _has_column(inspector) -> bool:
    return any(c["name"] == _TX_COLUMN for c in inspector.get_columns(_TX))


def upgrade() -> None:
    """Upgrade schema."""
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    tables = set(inspector.get_table_names())

    if _GROUPS in tables and _GROUP_INDEX not in _index_names(inspector, _GROUPS):
        conn.execute(
            sa.text(
                "UPDATE portfolio_groups SET is_default = :false WHERE is_default = :true "
                "AND id NOT IN (SELECT MIN(id) FROM portfolio_groups WHERE is_default = :true GROUP BY user_id)"
            ),
            {"true": True, "false": False},
        )
        op.create_index(
            _GROUP_INDEX,
            _GROUPS,
            ["user_id"],
            unique=True,
            sqlite_where=sa.text("is_default = 1"),
            postgresql_where=sa.text("is_default"),
        )

    if _TX in tables:
        if not _has_column(inspector):
            with op.batch_alter_table(_TX, schema=None) as batch_op:
                batch_op.add_column(sa.Column(_TX_COLUMN, sa.String(64), nullable=True))
        if _TX_INDEX not in _index_names(inspector, _TX):
            op.create_index(_TX_INDEX, _TX, ["user_id", _TX_COLUMN], unique=True)


def downgrade() -> None:
    """Downgrade schema."""
    inspector = sa.inspect(op.get_bind())
    tables = set(inspector.get_table_names())

    if _GROUPS in tables and _GROUP_INDEX in _index_names(inspector, _GROUPS):
        op.drop_index(_GROUP_INDEX, table_name=_GROUPS)

    if _TX in tables:
        if _TX_INDEX in _index_names(inspector, _TX):
            op.drop_index(_TX_INDEX, table_name=_TX)
        if _has_column(inspector):
            with op.batch_alter_table(_TX, schema=None) as batch_op:
                batch_op.drop_column(_TX_COLUMN)
