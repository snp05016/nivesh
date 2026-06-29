"""Add PortfolioGroup and Transaction models

Revision ID: 163d22315728
Revises: g1h2i3j4k5l6
Create Date: 2026-06-29 06:48:54.732225

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.engine.reflection import Inspector


# revision identifiers, used by Alembic.
revision: str = '163d22315728'
down_revision: Union[str, Sequence[str], None] = 'g1h2i3j4k5l6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _table_exists(bind, table_name: str) -> bool:
    insp = Inspector.from_engine(bind)
    return table_name in insp.get_table_names()


def _column_exists(bind, table_name: str, column_name: str) -> bool:
    insp = Inspector.from_engine(bind)
    return any(c["name"] == column_name for c in insp.get_columns(table_name))


def upgrade() -> None:
    """Upgrade schema."""
    bind = op.get_bind()

    # --- youtube_video_summaries (may already exist on some deployments) ---
    if not _table_exists(bind, 'youtube_video_summaries'):
        op.create_table('youtube_video_summaries',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('video_id', sa.String(length=20), nullable=False),
        sa.Column('url', sa.Text(), nullable=False),
        sa.Column('title', sa.Text(), nullable=True),
        sa.Column('channel', sa.Text(), nullable=True),
        sa.Column('duration_seconds', sa.Integer(), nullable=True),
        sa.Column('transcript_hash', sa.String(length=64), nullable=True),
        sa.Column('transcript_source', sa.String(length=50), nullable=True),
        sa.Column('summary_provider', sa.String(length=50), nullable=True),
        sa.Column('summary_json', sa.Text(), nullable=True),
        sa.Column('timestamps_json', sa.Text(), nullable=True),
        sa.Column('raw_transcript_preview', sa.Text(), nullable=True),
        sa.Column('estimated_input_tokens', sa.Integer(), nullable=True),
        sa.Column('estimated_output_tokens', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.Column('last_accessed_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id')
        )
        with op.batch_alter_table('youtube_video_summaries', schema=None) as batch_op:
            batch_op.create_index(batch_op.f('ix_youtube_video_summaries_id'), ['id'], unique=False)
            batch_op.create_index(batch_op.f('ix_youtube_video_summaries_video_id'), ['video_id'], unique=True)

    # --- dividend_ledger (may already exist) ---
    if not _table_exists(bind, 'dividend_ledger'):
        op.create_table('dividend_ledger',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('portfolio_id', sa.Integer(), nullable=True),
        sa.Column('ticker', sa.String(length=30), nullable=False),
        sa.Column('amount', sa.Float(), nullable=False),
        sa.Column('ex_date', sa.String(length=20), nullable=True),
        sa.Column('payment_date', sa.String(length=20), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
        )
        with op.batch_alter_table('dividend_ledger', schema=None) as batch_op:
            batch_op.create_index('ix_dividend_ledger_user_ticker', ['user_id', 'ticker'], unique=False)

    # --- in_app_notifications (may already exist) ---
    if not _table_exists(bind, 'in_app_notifications'):
        op.create_table('in_app_notifications',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('type', sa.String(length=50), nullable=False),
        sa.Column('title', sa.String(length=200), nullable=False),
        sa.Column('body', sa.Text(), nullable=False),
        sa.Column('is_read', sa.Boolean(), nullable=True),
        sa.Column('action_url', sa.String(length=500), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
        )
        with op.batch_alter_table('in_app_notifications', schema=None) as batch_op:
            batch_op.create_index(batch_op.f('ix_in_app_notifications_id'), ['id'], unique=False)
            batch_op.create_index(batch_op.f('ix_in_app_notifications_user_id'), ['user_id'], unique=False)

    # --- portfolio_groups (new table for this migration) ---
    if not _table_exists(bind, 'portfolio_groups'):
        op.create_table('portfolio_groups',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=200), nullable=True),
        sa.Column('is_default', sa.Boolean(), server_default='1', nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
        )
        with op.batch_alter_table('portfolio_groups', schema=None) as batch_op:
            batch_op.create_index('ix_portfolio_groups_user_id', ['user_id'], unique=False)

    # --- tax_reports (may already exist) ---
    if not _table_exists(bind, 'tax_reports'):
        op.create_table('tax_reports',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('fy_year', sa.String(length=20), nullable=False),
        sa.Column('stcg', sa.Float(), nullable=True),
        sa.Column('ltcg', sa.Float(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', 'fy_year', name='uq_tax_report_user_fy')
        )

    # --- user_preferences (may already exist) ---
    if not _table_exists(bind, 'user_preferences'):
        op.create_table('user_preferences',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('theme', sa.String(length=50), nullable=True),
        sa.Column('alerts_enabled', sa.Boolean(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
        )
        with op.batch_alter_table('user_preferences', schema=None) as batch_op:
            batch_op.create_index(batch_op.f('ix_user_preferences_id'), ['id'], unique=False)
            batch_op.create_index(batch_op.f('ix_user_preferences_user_id'), ['user_id'], unique=True)

    # --- portfolio_transactions (new table, depends on portfolio_groups) ---
    if not _table_exists(bind, 'portfolio_transactions'):
        op.create_table('portfolio_transactions',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('group_id', sa.Integer(), nullable=True),
        sa.Column('ticker', sa.String(length=30), nullable=False),
        sa.Column('transaction_type', sa.String(length=20), nullable=False),
        sa.Column('quantity', sa.Float(), nullable=False),
        sa.Column('price', sa.Float(), nullable=False),
        sa.Column('fees', sa.Float(), server_default='0.0', nullable=True),
        sa.Column('date', sa.DateTime(), nullable=True),
        sa.Column('notes', sa.String(length=500), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['group_id'], ['portfolio_groups.id'], ),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
        )
        with op.batch_alter_table('portfolio_transactions', schema=None) as batch_op:
            batch_op.create_index('ix_portfolio_transactions_date', ['date'], unique=False)
            batch_op.create_index('ix_portfolio_transactions_group_id', ['group_id'], unique=False)
            batch_op.create_index('ix_portfolio_transactions_ticker', ['ticker'], unique=False)
            batch_op.create_index('ix_portfolio_transactions_user_id', ['user_id'], unique=False)

    # --- portfolio: add is_virtual and group_id columns if missing ---
    with op.batch_alter_table('portfolio', schema=None) as batch_op:
        if not _column_exists(bind, 'portfolio', 'is_virtual'):
            batch_op.add_column(sa.Column('is_virtual', sa.Boolean(), server_default='0', nullable=False))
        if not _column_exists(bind, 'portfolio', 'group_id'):
            batch_op.add_column(sa.Column('group_id', sa.Integer(), nullable=True))
            batch_op.create_index('ix_portfolio_group_id', ['group_id'], unique=False)

    # --- trade_journal: add is_virtual column if missing ---
    with op.batch_alter_table('trade_journal', schema=None) as batch_op:
        if not _column_exists(bind, 'trade_journal', 'is_virtual'):
            batch_op.add_column(sa.Column('is_virtual', sa.Boolean(), server_default='0', nullable=False))


def downgrade() -> None:
    """Downgrade schema."""
    bind = op.get_bind()

    with op.batch_alter_table('trade_journal', schema=None) as batch_op:
        if _column_exists(bind, 'trade_journal', 'is_virtual'):
            batch_op.drop_column('is_virtual')

    with op.batch_alter_table('portfolio', schema=None) as batch_op:
        if _column_exists(bind, 'portfolio', 'group_id'):
            batch_op.drop_index('ix_portfolio_group_id')
            batch_op.drop_column('group_id')
        if _column_exists(bind, 'portfolio', 'is_virtual'):
            batch_op.drop_column('is_virtual')

    if _table_exists(bind, 'portfolio_transactions'):
        with op.batch_alter_table('portfolio_transactions', schema=None) as batch_op:
            batch_op.drop_index('ix_portfolio_transactions_user_id')
            batch_op.drop_index('ix_portfolio_transactions_ticker')
            batch_op.drop_index('ix_portfolio_transactions_group_id')
            batch_op.drop_index('ix_portfolio_transactions_date')
        op.drop_table('portfolio_transactions')

    if _table_exists(bind, 'user_preferences'):
        with op.batch_alter_table('user_preferences', schema=None) as batch_op:
            batch_op.drop_index(batch_op.f('ix_user_preferences_user_id'))
            batch_op.drop_index(batch_op.f('ix_user_preferences_id'))
        op.drop_table('user_preferences')

    if _table_exists(bind, 'tax_reports'):
        op.drop_table('tax_reports')

    if _table_exists(bind, 'portfolio_groups'):
        with op.batch_alter_table('portfolio_groups', schema=None) as batch_op:
            batch_op.drop_index('ix_portfolio_groups_user_id')
        op.drop_table('portfolio_groups')

    if _table_exists(bind, 'in_app_notifications'):
        with op.batch_alter_table('in_app_notifications', schema=None) as batch_op:
            batch_op.drop_index(batch_op.f('ix_in_app_notifications_user_id'))
            batch_op.drop_index(batch_op.f('ix_in_app_notifications_id'))
        op.drop_table('in_app_notifications')

    if _table_exists(bind, 'dividend_ledger'):
        with op.batch_alter_table('dividend_ledger', schema=None) as batch_op:
            batch_op.drop_index('ix_dividend_ledger_user_ticker')
        op.drop_table('dividend_ledger')

    if _table_exists(bind, 'youtube_video_summaries'):
        with op.batch_alter_table('youtube_video_summaries', schema=None) as batch_op:
            batch_op.drop_index(batch_op.f('ix_youtube_video_summaries_video_id'))
            batch_op.drop_index(batch_op.f('ix_youtube_video_summaries_id'))
        op.drop_table('youtube_video_summaries')
