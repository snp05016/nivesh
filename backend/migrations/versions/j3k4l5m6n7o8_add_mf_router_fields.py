"""Add MF Router fields to mutual_funds table.

Adds scheme_code (unique), scheme_name, amc_name, sub_category, nav_date,
aum_cr, expense_ratio, returns_1y/3y/5y, risk_level, fund_manager,
is_direct_plan, is_growth_plan so the MF Router backend
(services/mutual_fund_service.py, routers/mutual_funds.py) can serve
richer mutual fund data. Legacy columns fund_name, amc, and category are
kept for backward compatibility.

Revision ID: j3k4l5m6n7o8
Revises: h2i3j4k5l6m7
Create Date: 2026-07-02
"""

from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy import inspect

from alembic import op

revision: str = "j3k4l5m6n7o8"
down_revision: Union[str, Sequence[str], None] = "h2i3j4k5l6m7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _existing_columns(table_name: str) -> set:
    bind = op.get_bind()
    inspector = inspect(bind)
    return {col["name"] for col in inspector.get_columns(table_name)}


def _existing_indexes(table_name: str) -> set:
    bind = op.get_bind()
    inspector = inspect(bind)
    return {ix["name"] for ix in inspector.get_indexes(table_name)}


_NEW_COLUMNS = [
    ("scheme_code", sa.String(length=30)),
    ("scheme_name", sa.String(length=200)),
    ("amc_name", sa.String(length=100)),
    ("sub_category", sa.String(length=50)),
    ("nav_date", sa.String(length=20)),
    ("aum_cr", sa.Float()),
    ("expense_ratio", sa.Float()),
    ("returns_1y", sa.Float()),
    ("returns_3y", sa.Float()),
    ("returns_5y", sa.Float()),
    ("risk_level", sa.String(length=20)),
    ("fund_manager", sa.String(length=100)),
    ("is_direct_plan", sa.Boolean()),
    ("is_growth_plan", sa.Boolean()),
]


def upgrade() -> None:
    """Upgrade schema (idempotent)."""
    existing = _existing_columns("mutual_funds")
    existing_indexes = _existing_indexes("mutual_funds")
    with op.batch_alter_table("mutual_funds", schema=None) as batch_op:
        for name, col_type in _NEW_COLUMNS:
            if name not in existing:
                batch_op.add_column(sa.Column(name, col_type, nullable=True))
        if "scheme_code" not in existing:
            batch_op.create_index(
                batch_op.f("ix_mutual_funds_scheme_code"),
                ["scheme_code"],
                unique=True,
            )
        elif "ix_mutual_funds_scheme_code" not in existing_indexes:
            batch_op.create_index(
                batch_op.f("ix_mutual_funds_scheme_code"),
                ["scheme_code"],
                unique=True,
            )
        if "scheme_name" not in existing:
            batch_op.create_index(
                batch_op.f("ix_mutual_funds_scheme_name"),
                ["scheme_name"],
                unique=False,
            )


def downgrade() -> None:
    """Downgrade schema."""
    existing = _existing_columns("mutual_funds")
    with op.batch_alter_table("mutual_funds", schema=None) as batch_op:
        if "scheme_name" in existing:
            batch_op.drop_index(batch_op.f("ix_mutual_funds_scheme_name"))
        if "scheme_code" in existing:
            batch_op.drop_index(batch_op.f("ix_mutual_funds_scheme_code"))
        for name, _ in reversed(_NEW_COLUMNS):
            if name in existing:
                batch_op.drop_column(name)
