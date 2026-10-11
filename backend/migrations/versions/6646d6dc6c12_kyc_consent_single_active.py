"""At most one active KYC consent per user and type (DB-10)

Repeated grants used to insert one active row each, and a withdrawal revoked
only the newest, so the consent stayed active.

upgrade: revokes (revoked_at = now) every older duplicate active row, keeping
the highest id per (user_id, consent_type), then creates the partial unique
index uq_kyc_consents_active on kyc_consents(user_id, consent_type) WHERE
granted AND revoked_at IS NULL. Rows are never deleted. Skipped when the
index already exists.

downgrade: drops the index if present. Revoked duplicates stay revoked.

Revision ID: 6646d6dc6c12
Revises: 3e42e1828de8
Create Date: 2026-10-11
"""
from datetime import datetime, timezone
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "6646d6dc6c12"
down_revision: Union[str, Sequence[str], None] = "3e42e1828de8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TABLE = "kyc_consents"
_INDEX = "uq_kyc_consents_active"


def _index_exists(inspector) -> bool:
    return any(ix.get("name") == _INDEX for ix in inspector.get_indexes(_TABLE))


def upgrade() -> None:
    """Upgrade schema."""
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    if _TABLE not in inspector.get_table_names() or _index_exists(inspector):
        return

    conn.execute(
        sa.text(
            "UPDATE kyc_consents SET revoked_at = :now "
            "WHERE granted = :true AND revoked_at IS NULL AND id NOT IN ("
            "SELECT MAX(id) FROM kyc_consents WHERE granted = :true AND revoked_at IS NULL "
            "GROUP BY user_id, consent_type)"
        ),
        {"now": datetime.now(timezone.utc).replace(tzinfo=None), "true": True},
    )
    op.create_index(
        _INDEX,
        _TABLE,
        ["user_id", "consent_type"],
        unique=True,
        sqlite_where=sa.text("granted = 1 AND revoked_at IS NULL"),
        postgresql_where=sa.text("granted AND revoked_at IS NULL"),
    )


def downgrade() -> None:
    """Downgrade schema."""
    inspector = sa.inspect(op.get_bind())
    if _TABLE in inspector.get_table_names() and _index_exists(inspector):
        op.drop_index(_INDEX, table_name=_TABLE)
