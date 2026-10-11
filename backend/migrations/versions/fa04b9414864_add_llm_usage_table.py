"""Add llm_usage table (LLM-02 spend ledger)

One row per paid LLM call, identical to the LlmUsage model in models/db_models.py.
services/llm_budget.py sums it for the per-user and global daily AI budgets.

Idempotent: the table is created only if it does not exist (fresh databases get it
from Base.metadata.create_all), and downgrade drops it only if it exists.

Revision ID: fa04b9414864
Revises: f32cf73ca308
Create Date: 2026-10-11
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "fa04b9414864"
down_revision: Union[str, Sequence[str], None] = "f32cf73ca308"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    conn = op.get_bind()
    if "llm_usage" in set(sa.inspect(conn).get_table_names()):
        return
    op.create_table(
        "llm_usage",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("feature", sa.String(length=64), nullable=False),
        sa.Column("model", sa.String(length=80), nullable=False),
        sa.Column("input_tokens", sa.Integer(), nullable=False),
        sa.Column("output_tokens", sa.Integer(), nullable=False),
        sa.Column("cache_read_tokens", sa.Integer(), nullable=False),
        sa.Column("cache_write_tokens", sa.Integer(), nullable=False),
        sa.Column("cost_usd", sa.Float(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_llm_usage_created_at", "llm_usage", ["created_at"], unique=False)
    op.create_index("ix_llm_usage_user_created", "llm_usage", ["user_id", "created_at"], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    conn = op.get_bind()
    if "llm_usage" in set(sa.inspect(conn).get_table_names()):
        op.drop_table("llm_usage")
