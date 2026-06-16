"""Add missing columns to trade_journal and analysis_history for pre-existing databases.

These columns were added to the ORM models but never had corresponding Alembic migrations,
so any database created before these additions is MISSING them. This migration is
idempotent: columns that already exist (e.g. added by Base.metadata.create_all()) are
skipped so the migration does not error on partially-migrated databases.

Revision ID: a1b2c3d4e5f6
Revises: 1ad82d60efcc
Create Date: 2026-06-16

Tables affected:
- trade_journal: company_name, mood, updated_at
- analysis_history: outcome_delta_pct, was_correct, outcome_checked_at,
                    market_regime, calibrated_confidence, confidence_math_breakdown,
                    conformal_target_upper_3m, conformal_target_lower_3m,
                    quantitative_drivers, tail_risk_flags
"""

from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy import Boolean, DateTime, Float, JSON, String, inspect

from alembic import op


revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, Sequence[str], None] = "1ad82d60efcc"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _existing_columns(table_name: str) -> set[str]:
    """Return the set of column names currently in *table_name*."""
    bind = op.get_bind()
    inspector = inspect(bind)
    return {col["name"] for col in inspector.get_columns(table_name)}


def upgrade() -> None:
    # --------------------------------------------------------------------------
    # trade_journal — add company_name, mood, updated_at
    # --------------------------------------------------------------------------
    tj_existing = _existing_columns("trade_journal")
    tj_new_cols = []
    if "company_name" not in tj_existing:
        tj_new_cols.append(sa.Column("company_name", String(200), nullable=True))
    if "mood" not in tj_existing:
        tj_new_cols.append(sa.Column("mood", String(30), nullable=True))
    if "updated_at" not in tj_existing:
        tj_new_cols.append(sa.Column("updated_at", DateTime, nullable=True))

    if tj_new_cols:
        with op.batch_alter_table("trade_journal") as batch_op:
            for col in tj_new_cols:
                batch_op.add_column(col)

    # --------------------------------------------------------------------------
    # analysis_history — add epistemic feedback loop + ML hybrid pipeline cols
    # --------------------------------------------------------------------------
    ah_existing = _existing_columns("analysis_history")

    # (column_name, Column definition)
    ah_candidates = [
        # Epistemic feedback loop (added 2026-06-03)
        ("outcome_delta_pct",          sa.Column("outcome_delta_pct", Float, nullable=True)),
        ("was_correct",                sa.Column("was_correct", Boolean, nullable=True)),
        ("outcome_checked_at",         sa.Column("outcome_checked_at", DateTime, nullable=True)),
        # ML Hybrid Pipeline — quantitative engine columns (added 2026-06-14)
        ("market_regime",              sa.Column("market_regime", String, nullable=True)),
        ("calibrated_confidence",      sa.Column("calibrated_confidence", Float, nullable=True, server_default="0.0")),
        ("confidence_math_breakdown",  sa.Column("confidence_math_breakdown", JSON, nullable=True, server_default="{}")),
        ("conformal_target_upper_3m",  sa.Column("conformal_target_upper_3m", Float, nullable=True)),
        ("conformal_target_lower_3m",  sa.Column("conformal_target_lower_3m", Float, nullable=True)),
        ("quantitative_drivers",       sa.Column("quantitative_drivers", JSON, nullable=True, server_default="{}")),
        ("tail_risk_flags",            sa.Column("tail_risk_flags", JSON, nullable=True, server_default="{}")),
    ]
    ah_new_cols = [col for name, col in ah_candidates if name not in ah_existing]

    if ah_new_cols:
        with op.batch_alter_table("analysis_history") as batch_op:
            for col in ah_new_cols:
                batch_op.add_column(col)


def downgrade() -> None:
    # --------------------------------------------------------------------------
    # analysis_history — remove ML hybrid pipeline + epistemic feedback columns
    # (only drop if they exist, for symmetry with the idempotent upgrade)
    # --------------------------------------------------------------------------
    ah_existing = _existing_columns("analysis_history")
    ah_drop = [
        "tail_risk_flags", "quantitative_drivers",
        "conformal_target_lower_3m", "conformal_target_upper_3m",
        "confidence_math_breakdown", "calibrated_confidence",
        "market_regime", "outcome_checked_at", "was_correct", "outcome_delta_pct",
    ]
    ah_to_drop = [c for c in ah_drop if c in ah_existing]
    if ah_to_drop:
        with op.batch_alter_table("analysis_history") as batch_op:
            for col in ah_to_drop:
                batch_op.drop_column(col)

    # --------------------------------------------------------------------------
    # trade_journal — remove company_name, mood, updated_at
    # --------------------------------------------------------------------------
    tj_existing = _existing_columns("trade_journal")
    tj_drop = ["updated_at", "mood", "company_name"]
    tj_to_drop = [c for c in tj_drop if c in tj_existing]
    if tj_to_drop:
        with op.batch_alter_table("trade_journal") as batch_op:
            for col in tj_to_drop:
                batch_op.drop_column(col)
