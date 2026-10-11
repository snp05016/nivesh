"""At most one completed disbursement per loan application (GH-670)

Adds the partial unique index uq_loan_disbursement_completed_per_app on
loan_disbursements(loan_application_id) WHERE status = 'completed', the
database backstop for disburse_loan()'s atomic approved->disbursed claim.

upgrade: skipped if the table is missing or the index already exists. If any
application already has more than one completed row the upgrade stops with
an error naming the ids: those are money records and must be reconciled by
hand, never auto-deleted.

downgrade: drops the index if present.

Revision ID: 4aa54575a6f3
Revises: 117b4057d650
Create Date: 2026-10-11
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "4aa54575a6f3"
down_revision: Union[str, Sequence[str], None] = "117b4057d650"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TABLE = "loan_disbursements"
_INDEX = "uq_loan_disbursement_completed_per_app"
_WHERE = "status = 'completed'"


def _index_exists(inspector) -> bool:
    return any(ix.get("name") == _INDEX for ix in inspector.get_indexes(_TABLE))


def upgrade() -> None:
    """Upgrade schema."""
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    if _TABLE not in inspector.get_table_names() or _index_exists(inspector):
        return

    dupes = [
        row[0]
        for row in conn.execute(sa.text(
            "SELECT loan_application_id FROM loan_disbursements WHERE status = 'completed' "
            "GROUP BY loan_application_id HAVING COUNT(*) > 1"
        ))
    ]
    if dupes:
        raise RuntimeError(
            f"loan applications with more than one completed disbursement: {dupes}; "
            "reconcile these rows manually, then re-run the migration."
        )

    op.create_index(
        _INDEX,
        _TABLE,
        ["loan_application_id"],
        unique=True,
        sqlite_where=sa.text(_WHERE),
        postgresql_where=sa.text(_WHERE),
    )


def downgrade() -> None:
    """Downgrade schema."""
    inspector = sa.inspect(op.get_bind())
    if _TABLE in inspector.get_table_names() and _index_exists(inspector):
        op.drop_index(_INDEX, table_name=_TABLE)
