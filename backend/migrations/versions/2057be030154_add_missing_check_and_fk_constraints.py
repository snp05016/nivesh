"""Add model-declared CHECK and FK constraints missing from migrated DBs (DB-08)

Databases upgraded through the old migration chain (instead of the frozen
baseline) lack constraints the models declare: ck_portfolio_shares_positive,
ck_portfolio_buy_price_positive, ck_price_targets_positive, the FK
portfolio.group_id -> portfolio_groups.id and the FK
portfolio_valuation_history.user_id -> users.id. portfolio_transactions also
gets new CHECKs: quantity >= 0, price >= 0 and a transaction_type whitelist
(ADJUST included; close_position writes an ADJUST to 0 shares).

upgrade: every constraint is skipped when already present (fresh databases
built from the baseline). Rows that would violate a new CHECK stop the
upgrade with an error and counts, never a silent delete; fix those rows by
hand and re-run. Two safe cleanups run before the FKs: orphan
portfolio.group_id values are set to NULL, and portfolio_valuation_history
rows of users that no longer exist (derived snapshots) are deleted.
The device-binding unique key is already handled by ec35eaf96b81 and the
multi_asset_transactions CHECKs by 87e47e3f25d3.

downgrade: drops only the portfolio_transactions CHECKs this revision
introduced. The others are part of the baseline schema, so dropping them
would make a fresh database diverge from the models.

Revision ID: 2057be030154
Revises: 61bba5810e8e
Create Date: 2026-10-11
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "2057be030154"
down_revision: Union[str, Sequence[str], None] = "61bba5810e8e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TX_TYPES = "('BUY','SELL','SPLIT','BONUS','DIVIDEND','ADJUST')"

# table -> {check name: (CHECK expression, SQL WHERE matching violating rows)}
_CHECKS = {
    "portfolio": {
        "ck_portfolio_shares_positive": (
            "group_name = 'watchlist' OR shares > 0",
            "group_name <> 'watchlist' AND shares <= 0",
        ),
        "ck_portfolio_buy_price_positive": (
            "group_name = 'watchlist' OR buy_price > 0",
            "group_name <> 'watchlist' AND buy_price <= 0",
        ),
    },
    "price_targets": {
        "ck_price_targets_positive": ("target_price > 0", "target_price <= 0"),
    },
    "portfolio_transactions": {
        "ck_portfolio_transactions_quantity_nonneg": ("quantity >= 0", "quantity < 0"),
        "ck_portfolio_transactions_price_nonneg": ("price >= 0", "price < 0"),
        "ck_portfolio_transactions_type": (
            f"transaction_type IN {_TX_TYPES}",
            f"transaction_type NOT IN {_TX_TYPES}",
        ),
    },
}

# (table, column, referred table, constraint name, cleanup SQL run before creating it)
_FKS = [
    (
        "portfolio", "group_id", "portfolio_groups", "fk_portfolio_group_id",
        "UPDATE portfolio SET group_id = NULL WHERE group_id IS NOT NULL "
        "AND group_id NOT IN (SELECT id FROM portfolio_groups)",
    ),
    (
        "portfolio_valuation_history", "user_id", "users", "fk_portfolio_valuation_history_user_id",
        "DELETE FROM portfolio_valuation_history WHERE user_id NOT IN (SELECT id FROM users)",
    ),
]


def _check_names(inspector, table: str) -> set:
    return {c.get("name") for c in inspector.get_check_constraints(table)}


def _has_fk(inspector, table: str, column: str, referred: str) -> bool:
    return any(
        fk.get("referred_table") == referred and list(fk.get("constrained_columns") or []) == [column]
        for fk in inspector.get_foreign_keys(table)
    )


def upgrade() -> None:
    """Upgrade schema."""
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    tables = set(inspector.get_table_names())

    missing_checks = {
        table: [name for name in checks if name not in _check_names(inspector, table)]
        for table, checks in _CHECKS.items()
        if table in tables
    }
    violations = {}
    for table, names in missing_checks.items():
        for name in names:
            bad = conn.execute(sa.text(f"SELECT COUNT(*) FROM {table} WHERE {_CHECKS[table][name][1]}")).scalar() or 0
            if bad:
                violations[name] = bad
    if violations:
        raise RuntimeError(
            f"rows violating the new CHECK constraints (constraint: rows): {violations}; "
            "fix or delete them manually, then re-run the migration."
        )

    missing_fks = [
        fk for fk in _FKS
        if fk[0] in tables and fk[2] in tables and not _has_fk(inspector, fk[0], fk[1], fk[2])
    ]
    for table, _col, _ref, _name, cleanup in missing_fks:
        conn.execute(sa.text(cleanup))

    for table in _CHECKS:
        names = missing_checks.get(table) or []
        fks = [fk for fk in missing_fks if fk[0] == table]
        if not names and not fks:
            continue
        with op.batch_alter_table(table, schema=None) as batch_op:
            for name in names:
                batch_op.create_check_constraint(name, _CHECKS[table][name][0])
            for _table, col, ref, fk_name, _cleanup in fks:
                batch_op.create_foreign_key(fk_name, ref, [col], ["id"])

    for table, col, ref, fk_name, _cleanup in (fk for fk in missing_fks if fk[0] not in _CHECKS):
        with op.batch_alter_table(table, schema=None) as batch_op:
            batch_op.create_foreign_key(fk_name, ref, [col], ["id"])


def downgrade() -> None:
    """Downgrade schema."""
    inspector = sa.inspect(op.get_bind())
    table = "portfolio_transactions"
    if table not in inspector.get_table_names():
        return
    present = [name for name in _CHECKS[table] if name in _check_names(inspector, table)]
    if not present:
        return
    with op.batch_alter_table(table, schema=None) as batch_op:
        for name in present:
            batch_op.drop_constraint(name, type_="check")
