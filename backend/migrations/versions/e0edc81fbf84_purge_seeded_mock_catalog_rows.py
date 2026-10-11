"""Purge seeded mock mutual-fund and IPO rows (FAKE-06)

The public GET handlers used to seed illustrative catalogs on first read,
so existing databases hold invented NAVs/returns for six real schemes and
three fictional IPOs. Seeding now happens only at startup with DEMO_MODE=true;
this data migration deletes the previously seeded rows. Literals are copied
from services/mutual_fund_service._MOCK_FUNDS and ipo_service._MOCK_IPOS so
the migration does not depend on application code. No foreign keys point at
either table.

Idempotent: deleting already-absent rows is a no-op, and tables are checked
for existence first. Downgrade does nothing (fabricated data is not restored;
a demo server re-seeds at startup when DEMO_MODE=true).

Revision ID: e0edc81fbf84
Revises: e3c2837fd058
Create Date: 2026-10-11
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "e0edc81fbf84"
down_revision: Union[str, Sequence[str], None] = "e3c2837fd058"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_MOCK_SCHEME_CODES = (
    "INF209K01157",
    "INF090I01239",
    "INF109K01AA1",
    "INF204K01LX0",
    "INF200K01UY1",
    "INF769K01AJ4",
)
_MOCK_IPO_SYMBOLS = ("NOVAFIN", "SUNLOG", "BPRECIS")


def upgrade() -> None:
    """Delete the seeded mock catalog rows."""
    conn = op.get_bind()
    existing_tables = set(sa.inspect(conn).get_table_names())

    if "mutual_funds" in existing_tables:
        conn.execute(
            sa.text("DELETE FROM mutual_funds WHERE scheme_code IN :codes").bindparams(
                sa.bindparam("codes", expanding=True)
            ),
            {"codes": list(_MOCK_SCHEME_CODES)},
        )
    if "ipo_listings" in existing_tables:
        conn.execute(
            sa.text("DELETE FROM ipo_listings WHERE symbol IN :symbols").bindparams(
                sa.bindparam("symbols", expanding=True)
            ),
            {"symbols": list(_MOCK_IPO_SYMBOLS)},
        )


def downgrade() -> None:
    """No-op: deleted mock rows are not restored."""
    pass
