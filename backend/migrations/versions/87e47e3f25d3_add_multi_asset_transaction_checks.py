"""Add CHECK constraints to multi_asset_transactions (GH-646)

Mirrors the CheckConstraints on PortfolioTransaction in models/db_models.py:
positive quantity, non-negative price and fees, and the allowed asset_type /
transaction_type values.

Idempotent: constraints already present (fresh databases built by the initial
revision's create_all) are skipped, and downgrade drops only constraints that
exist. If existing rows violate the new rules the upgrade stops with an error
instead of deleting data; clean those rows manually and re-run.

Revision ID: 87e47e3f25d3
Revises: 36e47c594dc7
Create Date: 2026-10-11
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "87e47e3f25d3"
down_revision: Union[str, Sequence[str], None] = "36e47c594dc7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TABLE = "multi_asset_transactions"

_CHECKS = {
    "ck_multi_asset_tx_quantity_positive": "quantity > 0",
    "ck_multi_asset_tx_price_nonneg": "price >= 0",
    "ck_multi_asset_tx_fees_nonneg": "fees >= 0",
    "ck_multi_asset_tx_asset_type": "asset_type IN ('STOCK','MF','GOLD','FD')",
    "ck_multi_asset_tx_type": "transaction_type IN ('BUY','SELL','DEPOSIT','WITHDRAWAL','MATURITY')",
}

_VIOLATIONS_SQL = sa.text(
    f"SELECT COUNT(*) FROM {_TABLE} WHERE quantity <= 0 OR price < 0 OR fees < 0 "
    "OR asset_type NOT IN ('STOCK','MF','GOLD','FD') "
    "OR transaction_type NOT IN ('BUY','SELL','DEPOSIT','WITHDRAWAL','MATURITY')"
)


def _existing_checks(inspector) -> set:
    return {c.get("name") for c in inspector.get_check_constraints(_TABLE)}


def upgrade() -> None:
    """Upgrade schema."""
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    if _TABLE not in set(inspector.get_table_names()):
        return

    missing = [name for name in _CHECKS if name not in _existing_checks(inspector)]
    if not missing:
        return

    bad_rows = conn.execute(_VIOLATIONS_SQL).scalar() or 0
    if bad_rows:
        raise RuntimeError(
            f"{bad_rows} {_TABLE} rows violate the new CHECK constraints; "
            "clean them manually, then re-run the migration."
        )

    with op.batch_alter_table(_TABLE, schema=None) as batch_op:
        for name in missing:
            batch_op.create_check_constraint(name, _CHECKS[name])


def downgrade() -> None:
    """Downgrade schema."""
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    if _TABLE not in set(inspector.get_table_names()):
        return

    present = [name for name in _CHECKS if name in _existing_checks(inspector)]
    if not present:
        return

    with op.batch_alter_table(_TABLE, schema=None) as batch_op:
        for name in present:
            batch_op.drop_constraint(name, type_="check")
