"""Add IPO Hub fields to ipo_listings table.

Adds price_band_low/high, lot_size, issue_size_cr, status, subscription_qib/
nii/retail, and gmp columns so the IPO Hub backend (services/ipo_service.py,
routers/ipo.py) can serve richer IPO data. Legacy columns issue_price_min,
issue_price_max, and subscription_status are kept for backward compatibility.

Revision ID: h2i3j4k5l6m7
Revises: 04d52ed78b11
Create Date: 2026-07-02
"""

from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy import inspect

from alembic import op

revision: str = "h2i3j4k5l6m7"
down_revision: Union[str, Sequence[str], None] = "04d52ed78b11"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _existing_columns(table_name: str) -> set:
    bind = op.get_bind()
    inspector = inspect(bind)
    return {col["name"] for col in inspector.get_columns(table_name)}


_NEW_COLUMNS = [
    ("price_band_low", sa.Float()),
    ("price_band_high", sa.Float()),
    ("lot_size", sa.Integer()),
    ("issue_size_cr", sa.Float()),
    ("status", sa.String(length=20)),
    ("subscription_qib", sa.Float()),
    ("subscription_nii", sa.Float()),
    ("subscription_retail", sa.Float()),
    ("gmp", sa.Float()),
]


def upgrade() -> None:
    """Upgrade schema (idempotent)."""
    existing = _existing_columns("ipo_listings")
    with op.batch_alter_table("ipo_listings", schema=None) as batch_op:
        for name, col_type in _NEW_COLUMNS:
            if name not in existing:
                batch_op.add_column(sa.Column(name, col_type, nullable=True))
        if "status" not in existing:
            batch_op.create_index(
                batch_op.f("ix_ipo_listings_status"), ["status"], unique=False
            )


def downgrade() -> None:
    """Downgrade schema."""
    existing = _existing_columns("ipo_listings")
    with op.batch_alter_table("ipo_listings", schema=None) as batch_op:
        if "status" in existing:
            batch_op.drop_index(batch_op.f("ix_ipo_listings_status"))
        for name, _ in reversed(_NEW_COLUMNS):
            if name in existing:
                batch_op.drop_column(name)
