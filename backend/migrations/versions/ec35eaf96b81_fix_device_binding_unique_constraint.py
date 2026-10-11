"""Move uq_device_binding_user_device to device_bindings (GH-664)

The ORM used to declare the (user_id, device_id) unique constraint on the
append-only device_binding_attempts audit log instead of device_bindings.
Databases whose tables were built by create_all() got it on the wrong table,
so a second bind of the same device raised IntegrityError when the second
"bound" attempt row was logged.

upgrade: drop the constraint from device_binding_attempts if present, then add
it to device_bindings if missing. Duplicate (user_id, device_id) rows in
device_bindings stop the upgrade with an error instead of being deleted.
Alembic-built databases already match and are left unchanged.

downgrade: no-op. Re-adding the constraint to the audit log would bring the
bug back.

Revision ID: ec35eaf96b81
Revises: 87e47e3f25d3
Create Date: 2026-10-11
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "ec35eaf96b81"
down_revision: Union[str, Sequence[str], None] = "87e47e3f25d3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_NAME = "uq_device_binding_user_device"
_COLUMNS = ["user_id", "device_id"]


def _matching_uniques(inspector, table: str) -> list:
    return [
        uc for uc in inspector.get_unique_constraints(table)
        if uc.get("name") == _NAME or list(uc.get("column_names") or []) == _COLUMNS
    ]


def upgrade() -> None:
    """Upgrade schema."""
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    tables = set(inspector.get_table_names())

    # Drop first: on Postgres the constraint name must be free before it is reused.
    if "device_binding_attempts" in tables:
        wrong = [uc["name"] for uc in _matching_uniques(inspector, "device_binding_attempts") if uc.get("name")]
        if wrong:
            with op.batch_alter_table("device_binding_attempts", schema=None) as batch_op:
                for name in wrong:
                    batch_op.drop_constraint(name, type_="unique")

    if "device_bindings" in tables and not _matching_uniques(inspector, "device_bindings"):
        dupes = conn.execute(sa.text(
            "SELECT COUNT(*) FROM (SELECT user_id, device_id FROM device_bindings "
            "GROUP BY user_id, device_id HAVING COUNT(*) > 1) AS d"
        )).scalar() or 0
        if dupes:
            raise RuntimeError(
                f"{dupes} duplicate (user_id, device_id) groups in device_bindings; "
                "remove the duplicates manually, then re-run the migration."
            )
        with op.batch_alter_table("device_bindings", schema=None) as batch_op:
            batch_op.create_unique_constraint(_NAME, _COLUMNS)


def downgrade() -> None:
    """Downgrade schema: intentionally a no-op (see module docstring)."""
