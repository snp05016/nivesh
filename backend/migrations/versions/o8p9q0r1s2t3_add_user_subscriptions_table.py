"""Add user_subscriptions table (premium tier / mock billing)

Adds user_subscriptions so the MOCK subscription backend
(services/subscription_service.py, routers/subscription.py) can track a
user's premium tier for the iOS Profile/Settings premium-account demo.

MOCK DATA — simulated for demo purposes, not a real integration. No real
payment processor or StoreKit purchase-completion flow is wired to this
table.

Revision ID: o8p9q0r1s2t3
Revises: n7o8p9q0r1s2
Create Date: 2026-07-03

NOTE (reviewer fix): originally authored concurrently with
n7o8p9q0r1s2_add_compliance_tables.py, both chained onto
m6n7o8p9q0r1 (the loan marketplace migration) with a colliding
revision id (n7o8p9q0r1s2). Re-chained onto the compliance
migration and given a new unique revision id to restore a single
linear Alembic history.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "o8p9q0r1s2t3"
down_revision: Union[str, Sequence[str], None] = "n7o8p9q0r1s2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_tables = set(inspector.get_table_names())

    if "user_subscriptions" not in existing_tables:
        op.create_table(
            "user_subscriptions",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("tier", sa.String(length=20), nullable=False, server_default="free"),
            sa.Column("billing_cycle", sa.String(length=20), nullable=True),
            sa.Column("started_at", sa.DateTime(), nullable=True),
            sa.Column("renews_at", sa.DateTime(), nullable=True),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default="1"),
            sa.Column("cancelled_at", sa.DateTime(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.Column("updated_at", sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("user_id", name="uq_user_subscriptions_user_id"),
            sa.CheckConstraint(
                "tier IN ('free','pro','super_pro')", name="ck_user_subscription_tier"
            ),
            sa.CheckConstraint(
                "billing_cycle IN ('monthly','annual') OR billing_cycle IS NULL",
                name="ck_user_subscription_billing_cycle",
            ),
        )
        with op.batch_alter_table("user_subscriptions", schema=None) as batch_op:
            batch_op.create_index(batch_op.f("ix_user_subscriptions_id"), ["id"], unique=False)
            batch_op.create_index(
                batch_op.f("ix_user_subscriptions_user_id"), ["user_id"], unique=False
            )


def downgrade() -> None:
    """Downgrade schema."""
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_tables = set(inspector.get_table_names())

    if "user_subscriptions" in existing_tables:
        with op.batch_alter_table("user_subscriptions", schema=None) as batch_op:
            batch_op.drop_index(batch_op.f("ix_user_subscriptions_user_id"))
            batch_op.drop_index(batch_op.f("ix_user_subscriptions_id"))
        op.drop_table("user_subscriptions")
