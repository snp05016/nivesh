"""Rename seeded mock lenders/FD issuers to fictional names (REG-05)

The demo loan and FD marketplaces were seeded with real RBI-regulated bank
and NBFC names carrying a '(mock)' suffix. Seeds now use clearly fictional
names; this data migration renames rows already in the database, including
loan_disbursements.nbfc_name (copied from the offer at disbursement time).
The mapping lives here only, so the migration does not depend on app code.

Idempotent: an UPDATE matching no rows is a no-op, and tables are checked for
existence first. Downgrade restores the previous names.

Revision ID: a8fd0770d4d1
Revises: 2ea37dafbdbc
Create Date: 2026-10-11
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "a8fd0770d4d1"
down_revision: Union[str, Sequence[str], None] = "2ea37dafbdbc"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_LENDERS = {
    "Bajaj Finserv (mock)": "Demo Lender A (fictional)",
    "HDB Financial Services (mock)": "Demo Lender B (fictional)",
    "LIC Housing Finance (mock)": "Demo Lender C (fictional)",
    "Tata Capital (mock)": "Demo Lender D (fictional)",
    "Muthoot Finance (mock)": "Demo Lender E (fictional)",
}
_ISSUERS = {
    "HDFC Bank (mock)": "Demo Bank A (fictional)",
    "SBI (mock)": "Demo Bank B (fictional)",
    "ICICI Bank (mock)": "Demo Bank C (fictional)",
    "Bajaj Finance (mock)": "Demo NBFC A (fictional)",
    "Shriram Finance (mock)": "Demo NBFC B (fictional)",
    "PNB Housing Finance (mock)": "Demo NBFC C (fictional)",
}
# (table, column, mapping)
_TARGETS = (
    ("loan_offers", "nbfc_name", _LENDERS),
    ("loan_disbursements", "nbfc_name", _LENDERS),
    ("fixed_deposit_schemes", "issuer_name", _ISSUERS),
)


def _rename(reverse: bool) -> None:
    conn = op.get_bind()
    existing_tables = set(sa.inspect(conn).get_table_names())
    for table, column, mapping in _TARGETS:
        if table not in existing_tables:
            continue
        stmt = sa.text(f"UPDATE {table} SET {column} = :new WHERE {column} = :old")
        for real, fictional in mapping.items():
            old, new = (fictional, real) if reverse else (real, fictional)
            conn.execute(stmt, {"old": old, "new": new})


def upgrade() -> None:
    """Replace real lender/issuer names with fictional ones."""
    _rename(reverse=False)


def downgrade() -> None:
    """Restore the previous '(mock)' names."""
    _rename(reverse=True)
