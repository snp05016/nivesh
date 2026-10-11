"""Purge unverified advisor data (REG-01)

GET /api/v1/ideas/advisors used to seed advisor_biographies with named real
analysts and SEBI registration numbers that no registry backs. advisor_insights
also holds stance rows from three YouTube channels that have no SEBI
registration. This revision deletes both. text_advisory_insights references
advisor_biographies, so it is emptied first.

Data only and idempotent: each DELETE runs only when its table exists, and a
re-run deletes nothing. downgrade() is a no-op because deleted rows cannot be
restored; take the database backup before upgrading.

Revision ID: 8bd11e06fbf4
Revises: 117b4057d650
Create Date: 2026-10-11
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "8bd11e06fbf4"
down_revision: Union[str, Sequence[str], None] = "117b4057d650"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Channel ids the advisor harvester tracked without any SEBI registration: the
# current and the earlier id of @FirstGlobalAdvisory, @neerajmarathe and the
# Valuepickr channel (@rupakroyc).
_UNREGISTERED_CHANNEL_IDS = (
    "UCAk_whGHM2aAiZZADLF_GOw",
    "UCfJkQXEUC8QH9LgPbaMFjdw",
    "UCBEHGVRm5ZG-NS4ZRbczxQQ",
    "UCW6f5RnBqJjT6PnFvYuSqkA",
    "UCH1q_xJFB5KPJ_d3IQHY9NA",
    "UCm7mXqe96V8pVBe5YMNsVaA",
)


def upgrade() -> None:
    """Delete the unverified advisor rows."""
    conn = op.get_bind()
    tables = set(sa.inspect(conn).get_table_names())
    if "text_advisory_insights" in tables:
        conn.execute(sa.text("DELETE FROM text_advisory_insights"))
    if "advisor_biographies" in tables:
        conn.execute(sa.text("DELETE FROM advisor_biographies"))
    if "advisor_insights" in tables:
        conn.execute(
            sa.text("DELETE FROM advisor_insights WHERE channel_id IN :ids").bindparams(
                sa.bindparam("ids", expanding=True)
            ),
            {"ids": list(_UNREGISTERED_CHANNEL_IDS)},
        )


def downgrade() -> None:
    """No-op: the deleted rows were unverified claims and cannot be restored."""
