"""user_preferences.preferred_language (en|hi) for glossary explanations

upgrade (each step skipped when already present): adds preferred_language
VARCHAR(10) NOT NULL DEFAULT 'en' and CHECK ck_user_preferences_preferred_language
(preferred_language IN ('en','hi')). Existing rows become 'en' through the
server default.

downgrade: drops the constraint and the column when present.

Revision ID: 5c2e9b7d41af
Revises: ea2f610ceb51
Create Date: 2026-10-19
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "5c2e9b7d41af"
down_revision: Union[str, Sequence[str], None] = "ea2f610ceb51"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TABLE = "user_preferences"
_COLUMN = "preferred_language"
_CHECK = "ck_user_preferences_preferred_language"


def _state():
    inspector = sa.inspect(op.get_bind())
    if _TABLE not in inspector.get_table_names():
        return None
    columns = {c["name"] for c in inspector.get_columns(_TABLE)}
    checks = {c.get("name") for c in inspector.get_check_constraints(_TABLE)}
    return _COLUMN in columns, _CHECK in checks


def upgrade() -> None:
    """Upgrade schema."""
    state = _state()
    if state is None:
        return
    has_column, has_check = state
    if has_column and has_check:
        return
    with op.batch_alter_table(_TABLE, schema=None) as batch_op:
        if not has_column:
            batch_op.add_column(
                sa.Column(_COLUMN, sa.String(10), nullable=False, server_default="en")
            )
        if not has_check:
            batch_op.create_check_constraint(_CHECK, "preferred_language IN ('en','hi')")


def downgrade() -> None:
    """Downgrade schema."""
    state = _state()
    if state is None:
        return
    has_column, has_check = state
    if not has_column and not has_check:
        return
    with op.batch_alter_table(_TABLE, schema=None) as batch_op:
        if has_check:
            batch_op.drop_constraint(_CHECK, type_="check")
        if has_column:
            batch_op.drop_column(_COLUMN)
