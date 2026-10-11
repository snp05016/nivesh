"""Add users.is_admin and users.token_version (AUTH-01).

Admin rights used to live in process memory, granted at scheduler start to
whoever held the usernames 'saumya' or 'nirav'. They are now the persisted
users.is_admin flag. Nobody is promoted by this migration: after upgrading,
run `python scripts/manage_users.py set-admin <owner username>`.
token_version (default 0) is bumped by `manage_users.py reset-password` and
is what JWT revocation (AUTH-13) checks.

Idempotent: each column is added only if missing (the initial revision runs
Base.metadata.create_all, so fresh databases already have them), and
downgrade drops only columns that exist.

Revision ID: 55ecd4916ce6
Revises: 8bd11e06fbf4
Create Date: 2026-10-11
"""
from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy import inspect

from alembic import op

revision: str = "55ecd4916ce6"
down_revision: Union[str, Sequence[str], None] = "8bd11e06fbf4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_NEW_COLUMNS = [
    ("is_admin", sa.Boolean()),
    ("token_version", sa.Integer()),
]


def _existing_columns() -> set:
    return {col["name"] for col in inspect(op.get_bind()).get_columns("users")}


def upgrade() -> None:
    """Upgrade schema (idempotent)."""
    existing = _existing_columns()
    missing = [(name, col_type) for name, col_type in _NEW_COLUMNS if name not in existing]
    if missing:
        with op.batch_alter_table("users") as batch_op:
            for name, col_type in missing:
                batch_op.add_column(sa.Column(name, col_type, nullable=False, server_default="0"))


def downgrade() -> None:
    """Downgrade schema (idempotent)."""
    existing = _existing_columns()
    present = [name for name, _ in reversed(_NEW_COLUMNS) if name in existing]
    if present:
        with op.batch_alter_table("users") as batch_op:
            for name in present:
                batch_op.drop_column(name)
