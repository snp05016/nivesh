"""At most one active data deletion request per user (DB-27)

request_account_deletion() checks for a pending/processing request and then
inserts, so two concurrent calls could both insert. This adds the partial
unique index uq_data_deletion_active on data_deletion_requests(user_id)
WHERE status IN ('pending','processing') as the database backstop; the service
treats the IntegrityError as "already requested". The completed-disbursement
backstop already exists (uq_loan_disbursement_completed_per_app, 4aa54575a6f3).

upgrade: skipped if the table is missing or the index already exists. Extra
active requests (all but MIN(id) per user) are marked 'cancelled' first; no row
is deleted.

downgrade: drops the index if present. Cancelled duplicates stay cancelled.

Revision ID: 2ea37dafbdbc
Revises: 814a5ca5bc07
Create Date: 2026-10-11
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "2ea37dafbdbc"
down_revision: Union[str, Sequence[str], None] = "814a5ca5bc07"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TABLE = "data_deletion_requests"
_INDEX = "uq_data_deletion_active"
_WHERE = "status IN ('pending','processing')"


def _index_exists(inspector) -> bool:
    return any(ix.get("name") == _INDEX for ix in inspector.get_indexes(_TABLE))


def upgrade() -> None:
    """Upgrade schema."""
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    if _TABLE not in inspector.get_table_names() or _index_exists(inspector):
        return

    conn.execute(sa.text(
        f"UPDATE {_TABLE} SET status = 'cancelled' WHERE {_WHERE} AND id NOT IN ("
        f"SELECT MIN(id) FROM {_TABLE} WHERE {_WHERE} GROUP BY user_id)"
    ))
    op.create_index(
        _INDEX,
        _TABLE,
        ["user_id"],
        unique=True,
        sqlite_where=sa.text(_WHERE),
        postgresql_where=sa.text(_WHERE),
    )


def downgrade() -> None:
    """Downgrade schema."""
    inspector = sa.inspect(op.get_bind())
    if _TABLE in inspector.get_table_names() and _index_exists(inspector):
        op.drop_index(_INDEX, table_name=_TABLE)
