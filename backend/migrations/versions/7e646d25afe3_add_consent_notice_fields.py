"""Add policy version, notice hash, purpose and app version to kyc_consents (FINSEC-09)

All four columns are nullable: rows written before this revision (or by
clients that send no policy version) keep NULL, meaning "unknown".

upgrade: adds each column only if missing; skipped if the table is missing.
downgrade: drops each column only if present.

Revision ID: 7e646d25afe3
Revises: 7b766cb99b86
Create Date: 2026-10-11
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "7e646d25afe3"
down_revision: Union[str, Sequence[str], None] = "7b766cb99b86"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TABLE = "kyc_consents"
_COLUMNS = (
    ("policy_version", sa.String(length=20)),
    ("notice_hash", sa.String(length=64)),
    ("purpose", sa.String(length=200)),
    ("app_version", sa.String(length=20)),
)


def _existing_columns(bind) -> set[str]:
    insp = sa.inspect(bind)
    if _TABLE not in insp.get_table_names():
        return set()
    return {c["name"] for c in insp.get_columns(_TABLE)}


def upgrade() -> None:
    """Upgrade schema."""
    bind = op.get_bind()
    if _TABLE not in sa.inspect(bind).get_table_names():
        return
    existing = _existing_columns(bind)
    missing = [(name, type_) for name, type_ in _COLUMNS if name not in existing]
    if not missing:
        return
    with op.batch_alter_table(_TABLE, schema=None) as batch_op:
        for name, type_ in missing:
            batch_op.add_column(sa.Column(name, type_, nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    existing = _existing_columns(op.get_bind())
    present = [name for name, _ in _COLUMNS if name in existing]
    if not present:
        return
    with op.batch_alter_table(_TABLE, schema=None) as batch_op:
        for name in reversed(present):
            batch_op.drop_column(name)
