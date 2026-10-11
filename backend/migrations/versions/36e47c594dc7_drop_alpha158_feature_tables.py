"""Drop the unused Alpha158 feature tables (ML-23)

alpha158_features and alpha158_features_normalized were written only by two
unscheduled experiments (services/nightly_pipeline.py and
tasks/alpha158_task.py, both removed) and read by nothing. The ml-engine
FeatureComputer is the single feature definition; the backend persists no
features.

Idempotent: upgrade drops each table only if it exists (indexes go with the
table); downgrade recreates them exactly as 931cb6d2cbb6 and cb0f4d2ce6e1 did,
only if missing.

Revision ID: 36e47c594dc7
Revises: t4u5v6w7x8y9
Create Date: 2026-10-11
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "36e47c594dc7"
down_revision: Union[str, Sequence[str], None] = "t4u5v6w7x8y9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    conn = op.get_bind()
    existing_tables = set(sa.inspect(conn).get_table_names())

    for table in ("alpha158_features_normalized", "alpha158_features"):
        if table in existing_tables:
            op.drop_table(table)


def downgrade() -> None:
    """Downgrade schema."""
    conn = op.get_bind()
    existing_tables = set(sa.inspect(conn).get_table_names())

    if "alpha158_features" not in existing_tables:
        op.create_table(
            "alpha158_features",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("ticker", sa.String(length=30), nullable=False),
            sa.Column("date", sa.String(length=20), nullable=False),
            sa.Column("features", sa.JSON(), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("ticker", "date", name="uq_alpha158_ticker_date"),
        )
        with op.batch_alter_table("alpha158_features", schema=None) as batch_op:
            batch_op.create_index(batch_op.f("ix_alpha158_features_date"), ["date"], unique=False)
            batch_op.create_index(batch_op.f("ix_alpha158_features_ticker"), ["ticker"], unique=False)

    if "alpha158_features_normalized" not in existing_tables:
        op.create_table(
            "alpha158_features_normalized",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("ticker", sa.String(length=30), nullable=False),
            sa.Column("date", sa.String(length=20), nullable=False),
            sa.Column("feature_name", sa.String(length=30), nullable=False),
            sa.Column("feature_value", sa.Float(), nullable=False),
            sa.Column("computed_at", sa.DateTime(), nullable=True),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint(
                "ticker", "date", "feature_name", name="uq_alpha158_norm_ticker_date_feature",
            ),
        )
        with op.batch_alter_table("alpha158_features_normalized", schema=None) as batch_op:
            batch_op.create_index(batch_op.f("ix_alpha158_features_normalized_date"), ["date"], unique=False)
            batch_op.create_index(batch_op.f("ix_alpha158_features_normalized_ticker"), ["ticker"], unique=False)
            batch_op.create_index("ix_alpha158_norm_feature_name", ["feature_name"], unique=False)
            batch_op.create_index("ix_alpha158_norm_ticker_date", ["ticker", "date"], unique=False)
