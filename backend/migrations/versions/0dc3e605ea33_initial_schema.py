"""initial_schema

Revision ID: 0dc3e605ea33
Revises: 
Create Date: 2026-06-16 05:40:37.823639

Frozen baseline (DB-07 / #457). This revision used to build the schema
from today's models at runtime, so a fresh
``alembic upgrade head`` silently built whatever the models said and every
later migration was skipped by its existence guard. The DDL below is the
schema rendered once from models/db_models.py (71 tables) and must never be
regenerated: schema changes go in a new revision chained to the head.
Do not import application models here.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0dc3e605ea33'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create the frozen baseline schema."""
    op.create_table(
        'users',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('username', sa.String(50), nullable=False, unique=True),
        sa.Column('password_hash', sa.String(64), nullable=False),
        sa.Column('display_name', sa.String(100), nullable=False),
        sa.Column('created_at', sa.DateTime()),
    )

    op.create_table(
        'portfolio_groups',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('name', sa.String(200)),
        sa.Column('is_default', sa.Boolean(), server_default='1'),
        sa.Column('created_at', sa.DateTime()),
    )
    op.create_index('ix_portfolio_groups_user_id', 'portfolio_groups', ['user_id'], unique=False)

    op.create_table(
        'portfolio',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('ticker', sa.String(30), nullable=False),
        sa.Column('company_name', sa.String(200), nullable=False),
        sa.Column('shares', sa.Float(), nullable=False),
        sa.Column('buy_price', sa.Float(), nullable=False),
        sa.Column('target_price', sa.Float(), nullable=True),
        sa.Column('purchase_date', sa.String(), nullable=True),
        sa.Column('group_name', sa.String(50)),
        sa.Column('notes', sa.Text()),
        sa.Column('is_virtual', sa.Boolean(), server_default='0', nullable=False),
        sa.Column('created_at', sa.DateTime()),
        sa.Column('group_id', sa.Integer(), sa.ForeignKey('portfolio_groups.id'), nullable=True),
        sa.UniqueConstraint('user_id', 'ticker', 'group_name', name='uq_portfolio_user_ticker_group'),
        sa.CheckConstraint("group_name = 'watchlist' OR shares > 0", name='ck_portfolio_shares_positive'),
        sa.CheckConstraint("group_name = 'watchlist' OR buy_price > 0", name='ck_portfolio_buy_price_positive'),
    )
    op.create_index('ix_portfolio_user_id', 'portfolio', ['user_id'], unique=False)
    op.create_index('ix_portfolio_user_ticker', 'portfolio', ['user_id', 'ticker'], unique=False)
    op.create_index('ix_portfolio_group', 'portfolio', ['user_id', 'group_name'], unique=False)
    op.create_index('ix_portfolio_group_id', 'portfolio', ['group_id'], unique=False)

    op.create_table(
        'portfolio_transactions',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('group_id', sa.Integer(), sa.ForeignKey('portfolio_groups.id'), nullable=True),
        sa.Column('ticker', sa.String(30), nullable=False),
        sa.Column('transaction_type', sa.String(20), nullable=False),
        sa.Column('quantity', sa.Float(), nullable=False),
        sa.Column('price', sa.Float(), nullable=False),
        sa.Column('fees', sa.Float(), server_default='0.0'),
        sa.Column('date', sa.DateTime()),
        sa.Column('notes', sa.String(500), nullable=True),
        sa.Column('created_at', sa.DateTime()),
    )
    op.create_index('ix_portfolio_transactions_user_id', 'portfolio_transactions', ['user_id'], unique=False)
    op.create_index('ix_portfolio_transactions_ticker', 'portfolio_transactions', ['ticker'], unique=False)
    op.create_index('ix_portfolio_transactions_group_id', 'portfolio_transactions', ['group_id'], unique=False)
    op.create_index('ix_portfolio_transactions_date', 'portfolio_transactions', ['date'], unique=False)

    op.create_table(
        'multi_asset_transactions',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('asset_type', sa.String(20), nullable=False),
        sa.Column('symbol', sa.String(50), nullable=False),
        sa.Column('transaction_type', sa.String(20), nullable=False),
        sa.Column('quantity', sa.Float(), nullable=False),
        sa.Column('price', sa.Float(), nullable=False),
        sa.Column('fees', sa.Float(), server_default='0.0'),
        sa.Column('date', sa.DateTime()),
        sa.Column('notes', sa.String(500), nullable=True),
        sa.Column('created_at', sa.DateTime()),
    )
    op.create_index('ix_multi_asset_transactions_user_id', 'multi_asset_transactions', ['user_id'], unique=False)
    op.create_index('ix_multi_asset_transactions_asset_type', 'multi_asset_transactions', ['asset_type'], unique=False)
    op.create_index('ix_multi_asset_transactions_symbol', 'multi_asset_transactions', ['symbol'], unique=False)
    op.create_index('ix_multi_asset_transactions_date', 'multi_asset_transactions', ['date'], unique=False)

    op.create_table(
        'analysis_history',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('ticker', sa.String(30), nullable=False),
        sa.Column('analysis_date', sa.String(20), nullable=False),
        sa.Column('signal', sa.String(20), nullable=False),
        sa.Column('confidence_pct', sa.Integer(), nullable=True),
        sa.Column('target_short', sa.Float(), nullable=True),
        sa.Column('target_medium', sa.Float(), nullable=True),
        sa.Column('target_long', sa.Float(), nullable=True),
        sa.Column('promoter_pledged_pct', sa.Float(), nullable=True),
        sa.Column('promoter_pledged_trend', sa.String(20), nullable=True),
        sa.Column('raw_output', sa.Text(), nullable=True),
        sa.Column('full_json', sa.Text(), nullable=False),
        sa.Column('scan_type', sa.String(20), nullable=False),
        sa.Column('outcome_delta_pct', sa.Float(), nullable=True),
        sa.Column('was_correct', sa.Boolean(), nullable=True),
        sa.Column('outcome_checked_at', sa.DateTime(), nullable=True),
        sa.Column('market_regime', sa.String(), nullable=True),
        sa.Column('calibrated_confidence', sa.Float(), server_default='0.0', nullable=True),
        sa.Column('confidence_math_breakdown', sa.JSON()),
        sa.Column('conformal_target_upper_3m', sa.Float(), nullable=True),
        sa.Column('conformal_target_lower_3m', sa.Float(), nullable=True),
        sa.Column('quantitative_drivers', sa.JSON()),
        sa.Column('tail_risk_flags', sa.JSON()),
        sa.Column('created_at', sa.DateTime()),
    )
    op.create_index('ix_analysis_history_user_id', 'analysis_history', ['user_id'], unique=False)
    op.create_index('ix_analysis_history_ticker', 'analysis_history', ['ticker'], unique=False)
    op.create_index('ix_analysis_history_scan_type', 'analysis_history', ['scan_type'], unique=False)
    op.create_index('ix_analysis_history_created_at', 'analysis_history', ['created_at'], unique=False)
    op.create_index('ix_analysis_history_ticker_user', 'analysis_history', ['ticker', 'user_id'], unique=False)

    op.create_table(
        'signal_events',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('ticker', sa.String(20), nullable=False),
        sa.Column('from_signal', sa.String(30), nullable=False),
        sa.Column('to_signal', sa.String(30), nullable=False),
        sa.Column('event_date', sa.String(20), nullable=False),
        sa.Column('created_at', sa.DateTime()),
    )
    op.create_index('ix_signal_events_ticker', 'signal_events', ['ticker'], unique=False)

    op.create_table(
        'analysis_jobs',
        sa.Column('job_id', sa.String(12), primary_key=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('ticker', sa.String(30), nullable=False),
        sa.Column('exchange', sa.String(10), nullable=False),
        sa.Column('scan_type', sa.String(20), nullable=False),
        sa.Column('status', sa.String(20), nullable=False),
        sa.Column('stage', sa.String(60), nullable=True),
        sa.Column('progress_pct', sa.Integer(), nullable=False),
        sa.Column('checkpoints', sa.Text(), nullable=False),
        sa.Column('pid', sa.Integer(), nullable=True),
        sa.Column('heartbeat_at', sa.DateTime(), nullable=True),
        sa.Column('tokens_used', sa.Integer(), nullable=False),
        sa.Column('error', sa.Text(), nullable=True),
        sa.Column('result_json', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime()),
        sa.Column('started_at', sa.DateTime(), nullable=True),
        sa.Column('finished_at', sa.DateTime(), nullable=True),
    )
    op.create_index('ix_analysis_jobs_user_id', 'analysis_jobs', ['user_id'], unique=False)
    op.create_index('ix_analysis_jobs_ticker', 'analysis_jobs', ['ticker'], unique=False)

    op.create_table(
        'price_targets',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('ticker', sa.String(30), nullable=False),
        sa.Column('target_price', sa.Float(), nullable=False),
        sa.Column('direction', sa.String(10), nullable=False),
        sa.Column('triggered', sa.Boolean()),
        sa.Column('created_at', sa.DateTime()),
        sa.CheckConstraint('target_price > 0', name='ck_price_targets_positive'),
    )
    op.create_index('ix_price_targets_user_id', 'price_targets', ['user_id'], unique=False)

    op.create_table(
        'trade_journal',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('ticker', sa.String(30), nullable=False),
        sa.Column('action', sa.String(10), nullable=False),
        sa.Column('price_at_time', sa.Float(), nullable=False),
        sa.Column('reason_text', sa.Text(), nullable=False),
        sa.Column('outcome_text', sa.Text(), nullable=True),
        sa.Column('company_name', sa.String(200), nullable=True),
        sa.Column('mood', sa.String(30), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.Column('is_virtual', sa.Boolean(), server_default='0', nullable=False),
        sa.Column('created_at', sa.DateTime()),
    )
    op.create_index('ix_trade_journal_user_id', 'trade_journal', ['user_id'], unique=False)

    op.create_table(
        'dividend_ledger',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('portfolio_id', sa.Integer(), nullable=True),
        sa.Column('ticker', sa.String(30), nullable=False),
        sa.Column('amount', sa.Float(), nullable=False),
        sa.Column('ex_date', sa.String(20), nullable=True),
        sa.Column('payment_date', sa.String(20), nullable=True),
        sa.Column('created_at', sa.DateTime()),
    )
    op.create_index('ix_dividend_ledger_user_ticker', 'dividend_ledger', ['user_id', 'ticker'], unique=False)

    op.create_table(
        'tax_reports',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('fy_year', sa.String(20), nullable=False),
        sa.Column('stcg', sa.Float()),
        sa.Column('ltcg', sa.Float()),
        sa.Column('created_at', sa.DateTime()),
        sa.Column('updated_at', sa.DateTime()),
        sa.UniqueConstraint('user_id', 'fy_year', name='uq_tax_report_user_fy'),
    )

    op.create_table(
        'device_tokens',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('device_token', sa.String(200), nullable=False, unique=True),
        sa.Column('platform', sa.String(10)),
        sa.Column('created_at', sa.DateTime()),
        sa.Column('updated_at', sa.DateTime()),
    )
    op.create_index('ix_device_tokens_user_id', 'device_tokens', ['user_id'], unique=False)

    op.create_table(
        'advisor_insights',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('ticker', sa.String(), nullable=False),
        sa.Column('advisor_name', sa.String(), nullable=False),
        sa.Column('channel_id', sa.String(), nullable=False),
        sa.Column('video_id', sa.String(), nullable=False),
        sa.Column('video_title', sa.String(), nullable=False),
        sa.Column('video_url', sa.String(), nullable=False),
        sa.Column('published_at', sa.DateTime(), nullable=False),
        sa.Column('transcript_source', sa.String(), nullable=False),
        sa.Column('stance', sa.String(), nullable=False),
        sa.Column('confidence', sa.String(), nullable=False),
        sa.Column('catalyst_summary', sa.String(), nullable=False),
        sa.Column('raw_snippet', sa.Text(), nullable=True),
        sa.Column('view_count', sa.Integer()),
        sa.Column('created_at', sa.DateTime()),
        sa.UniqueConstraint('video_id', 'ticker', name='uq_video_ticker'),
    )
    op.create_index('ix_advisor_insights_id', 'advisor_insights', ['id'], unique=False)
    op.create_index('ix_advisor_insights_ticker', 'advisor_insights', ['ticker'], unique=False)
    op.create_index('ix_advisor_ticker_published', 'advisor_insights', ['ticker', 'published_at'], unique=False)

    op.create_table(
        'news_articles',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('source', sa.String(), nullable=False),
        sa.Column('ticker', sa.String(), nullable=True),
        sa.Column('headline', sa.String(), nullable=False),
        sa.Column('summary', sa.Text(), nullable=True),
        sa.Column('body_text', sa.Text(), nullable=True),
        sa.Column('image_url', sa.String(), nullable=True),
        sa.Column('article_url', sa.String(), nullable=False, unique=True),
        sa.Column('published_at', sa.DateTime(), nullable=False),
        sa.Column('sentiment', sa.String(), nullable=True),
        sa.Column('sentiment_score', sa.Float(), nullable=True),
        sa.Column('sentiment_label', sa.String(), nullable=True),
        sa.Column('is_red_flag', sa.Boolean()),
        sa.Column('created_at', sa.DateTime()),
    )
    op.create_index('ix_news_articles_id', 'news_articles', ['id'], unique=False)
    op.create_index('ix_news_articles_ticker', 'news_articles', ['ticker'], unique=False)

    op.create_table(
        'youtube_videos',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('video_id', sa.String(), nullable=False, unique=True),
        sa.Column('channel_name', sa.String(), nullable=False),
        sa.Column('title', sa.String(), nullable=False),
        sa.Column('description_snippet', sa.String(), nullable=True),
        sa.Column('channel_url', sa.String(), nullable=True),
        sa.Column('thumbnail_url', sa.String(), nullable=True),
        sa.Column('video_url', sa.String(), nullable=False),
        sa.Column('published_at', sa.DateTime(), nullable=False),
        sa.Column('view_count', sa.Integer()),
        sa.Column('duration_seconds', sa.Integer()),
        sa.Column('tickers_mentioned', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime()),
        sa.Column('harvested_at', sa.DateTime()),
        sa.Column('matched_ticker', sa.String(), nullable=True),
        sa.Column('source', sa.String()),
        sa.Column('sebi_reg', sa.String(), nullable=True),
    )
    op.create_index('ix_youtube_videos_id', 'youtube_videos', ['id'], unique=False)
    op.create_index('ix_youtube_videos_matched_ticker', 'youtube_videos', ['matched_ticker'], unique=False)

    op.create_table(
        'portfolio_valuation_history',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id', name='fk_portfolio_valuation_history_user_id'), nullable=False),
        sa.Column('snapshot_date', sa.String(), nullable=False),
        sa.Column('total_value', sa.Float(), nullable=False),
        sa.Column('total_invested', sa.Float(), nullable=False),
        sa.Column('total_pnl', sa.Float(), nullable=False),
        sa.Column('pnl_percent', sa.Float(), nullable=False),
        sa.Column('nifty_close', sa.Float(), nullable=True),
        sa.Column('created_at', sa.DateTime()),
        sa.UniqueConstraint('user_id', 'snapshot_date', name='uq_user_date_snapshot'),
    )
    op.create_index('ix_portfolio_valuation_history_id', 'portfolio_valuation_history', ['id'], unique=False)
    op.create_index('ix_portfolio_valuation_history_user_id', 'portfolio_valuation_history', ['user_id'], unique=False)

    op.create_table(
        'pkscreener_signals',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('ticker', sa.String(), nullable=False),
        sa.Column('signal_date', sa.String(), nullable=False),
        sa.Column('screen_result', sa.String(), nullable=True),
        sa.Column('breakout', sa.Boolean()),
        sa.Column('consolidating', sa.Boolean()),
        sa.Column('rsi', sa.Float(), nullable=True),
        sa.Column('macd_signal', sa.String(), nullable=True),
        sa.Column('ma_signal', sa.String(), nullable=True),
        sa.Column('volume_signal', sa.String(), nullable=True),
        sa.Column('pattern', sa.String(), nullable=True),
        sa.Column('technical_score', sa.Float(), nullable=True),
        sa.Column('created_at', sa.DateTime()),
        sa.UniqueConstraint('ticker', 'signal_date', name='uq_ticker_date_signal'),
    )
    op.create_index('ix_pkscreener_signals_id', 'pkscreener_signals', ['id'], unique=False)
    op.create_index('ix_pkscreener_signals_ticker', 'pkscreener_signals', ['ticker'], unique=False)

    op.create_table(
        'macro_events',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('title', sa.String(300), nullable=False),
        sa.Column('event_date', sa.String(20), nullable=False),
        sa.Column('event_time', sa.String(10), nullable=True),
        sa.Column('impact', sa.String(10), nullable=False),
        sa.Column('consensus', sa.String(100), nullable=True),
        sa.Column('actual', sa.String(100), nullable=True),
        sa.Column('prior', sa.String(100), nullable=True),
        sa.Column('category', sa.String(50), nullable=True),
        sa.Column('source', sa.String(100), nullable=True),
        sa.Column('created_at', sa.DateTime()),
        sa.Column('updated_at', sa.DateTime()),
    )
    op.create_index('ix_macro_events_id', 'macro_events', ['id'], unique=False)
    op.create_index('ix_macro_events_date', 'macro_events', ['event_date'], unique=False)

    op.create_table(
        'net_worth_ledger',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('snapshot_date', sa.String(20), nullable=False),
        sa.Column('total_value_inr', sa.Float(), nullable=False),
        sa.Column('daily_delta_inr', sa.Float(), nullable=True),
        sa.Column('daily_delta_pct', sa.Float(), nullable=True),
        sa.Column('peak_value_inr', sa.Float(), nullable=True),
        sa.Column('top_gainer_ticker', sa.String(30), nullable=True),
        sa.Column('top_gainer_pct', sa.Float(), nullable=True),
        sa.Column('top_loser_ticker', sa.String(30), nullable=True),
        sa.Column('top_loser_pct', sa.Float(), nullable=True),
        sa.Column('portfolio_json', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime()),
        sa.UniqueConstraint('user_id', 'snapshot_date', name='uq_networth_user_date'),
    )
    op.create_index('ix_net_worth_ledger_id', 'net_worth_ledger', ['id'], unique=False)
    op.create_index('ix_net_worth_ledger_user_id', 'net_worth_ledger', ['user_id'], unique=False)

    op.create_table(
        'market_error_logs',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('timestamp', sa.DateTime()),
        sa.Column('component', sa.String(100), nullable=False),
        sa.Column('error_message', sa.Text(), nullable=False),
        sa.Column('context_ticker', sa.String(30), nullable=True),
    )
    op.create_index('ix_market_error_logs_id', 'market_error_logs', ['id'], unique=False)

    op.create_table(
        'earnings_alerts',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('ticker', sa.String(30), nullable=False),
        sa.Column('earnings_date', sa.String(20), nullable=False),
        sa.Column('created_at', sa.DateTime()),
        sa.UniqueConstraint('user_id', 'ticker', 'earnings_date', name='uq_user_ticker_earnings_date'),
    )
    op.create_index('ix_earnings_alerts_id', 'earnings_alerts', ['id'], unique=False)
    op.create_index('ix_earnings_alerts_user_id', 'earnings_alerts', ['user_id'], unique=False)

    op.create_table(
        'earnings_error_logs',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('timestamp', sa.DateTime()),
        sa.Column('module', sa.String(100), nullable=False),
        sa.Column('error_trace', sa.Text(), nullable=False),
        sa.Column('failed_ticker', sa.String(30), nullable=True),
    )
    op.create_index('ix_earnings_error_logs_id', 'earnings_error_logs', ['id'], unique=False)

    op.create_table(
        'block_deals',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('date', sa.String(20), nullable=False),
        sa.Column('ticker', sa.String(30), nullable=False),
        sa.Column('client_name', sa.String(200), nullable=False),
        sa.Column('deal_type', sa.String(20), nullable=False),
        sa.Column('quantity', sa.Integer(), nullable=False),
        sa.Column('price', sa.Float(), nullable=False),
        sa.Column('created_at', sa.DateTime()),
    )
    op.create_index('ix_block_deals_id', 'block_deals', ['id'], unique=False)
    op.create_index('ix_block_deals_date', 'block_deals', ['date'], unique=False)
    op.create_index('ix_block_deals_ticker', 'block_deals', ['ticker'], unique=False)

    op.create_table(
        'fii_dii_flow',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('date', sa.String(20), nullable=False),
        sa.Column('fii_buy', sa.Float(), nullable=False),
        sa.Column('fii_sell', sa.Float(), nullable=False),
        sa.Column('fii_net', sa.Float(), nullable=False),
        sa.Column('dii_buy', sa.Float(), nullable=False),
        sa.Column('dii_sell', sa.Float(), nullable=False),
        sa.Column('dii_net', sa.Float(), nullable=False),
        sa.Column('created_at', sa.DateTime()),
    )
    op.create_index('ix_fii_dii_flow_id', 'fii_dii_flow', ['id'], unique=False)
    op.create_index('ix_fii_dii_flow_date', 'fii_dii_flow', ['date'], unique=True)

    op.create_table(
        'notification_error_logs',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('timestamp', sa.DateTime()),
        sa.Column('failure_point', sa.String(100), nullable=False),
        sa.Column('error_trace', sa.Text(), nullable=False),
        sa.Column('target_device', sa.String(200), nullable=True),
    )
    op.create_index('ix_notification_error_logs_id', 'notification_error_logs', ['id'], unique=False)

    op.create_table(
        'advisor_biographies',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('advisor_name', sa.String(100), nullable=False),
        sa.Column('sebi_reg_number', sa.String(20), nullable=False, unique=True),
        sa.Column('experience_years', sa.Integer()),
        sa.Column('analytical_framework', sa.String(200), nullable=True),
        sa.Column('full_biography_text', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime()),
    )
    op.create_index('ix_advisor_biographies_id', 'advisor_biographies', ['id'], unique=False)
    op.create_index('ix_advisor_biographies_advisor_name', 'advisor_biographies', ['advisor_name'], unique=False)

    op.create_table(
        'text_advisory_insights',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('advisor_id', sa.Integer(), sa.ForeignKey('advisor_biographies.id'), nullable=False),
        sa.Column('timestamp', sa.DateTime()),
        sa.Column('content_text', sa.Text(), nullable=False),
        sa.Column('target_ticker', sa.String(30), nullable=True),
        sa.Column('extracted_sentiment', sa.String(20), nullable=True),
        sa.Column('source_url', sa.String(500), nullable=True),
    )
    op.create_index('ix_text_advisory_insights_id', 'text_advisory_insights', ['id'], unique=False)
    op.create_index('ix_text_advisory_insights_advisor_id', 'text_advisory_insights', ['advisor_id'], unique=False)
    op.create_index('ix_text_advisory_insights_target_ticker', 'text_advisory_insights', ['target_ticker'], unique=False)

    op.create_table(
        'ideas_error_logs',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('timestamp', sa.DateTime()),
        sa.Column('module', sa.String(100), nullable=False),
        sa.Column('error_trace', sa.Text(), nullable=False),
        sa.Column('context_ticker', sa.String(30), nullable=True),
    )
    op.create_index('ix_ideas_error_logs_id', 'ideas_error_logs', ['id'], unique=False)

    op.create_table(
        'market_anomalies',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('ticker', sa.String()),
        sa.Column('company', sa.String()),
        sa.Column('anomaly_type', sa.String()),
        sa.Column('severity', sa.String()),
        sa.Column('detail', sa.Text()),
        sa.Column('price', sa.Float()),
        sa.Column('change_pct', sa.Float()),
        sa.Column('timestamp', sa.DateTime()),
    )
    op.create_index('ix_market_anomalies_id', 'market_anomalies', ['id'], unique=False)
    op.create_index('ix_market_anomalies_anomaly_type', 'market_anomalies', ['anomaly_type'], unique=False)
    op.create_index('ix_market_anomalies_ticker', 'market_anomalies', ['ticker'], unique=False)
    op.create_index('ix_market_anomalies_timestamp', 'market_anomalies', ['timestamp'], unique=False)

    op.create_table(
        'earnings_surprise_history',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('ticker', sa.String()),
        sa.Column('company_name', sa.String()),
        sa.Column('quarter', sa.String()),
        sa.Column('estimated_eps', sa.Float()),
        sa.Column('actual_eps', sa.Float()),
        sa.Column('surprise_pct', sa.Float()),
        sa.Column('classification', sa.String()),
        sa.Column('post_price_1d', sa.Float()),
        sa.Column('post_price_5d', sa.Float()),
        sa.Column('historical_score', sa.Float()),
        sa.Column('serial_pattern', sa.String()),
        sa.Column('created_at', sa.DateTime()),
    )
    op.create_index('ix_earnings_surprise_history_id', 'earnings_surprise_history', ['id'], unique=False)
    op.create_index('ix_earnings_surprise_history_ticker', 'earnings_surprise_history', ['ticker'], unique=False)

    op.create_table(
        'equity_risk_factors',
        sa.Column('ticker', sa.String(30), primary_key=True),
        sa.Column('beta_market', sa.Float(), nullable=True),
        sa.Column('beta_oil', sa.Float(), nullable=True),
        sa.Column('beta_rates', sa.Float(), nullable=True),
        sa.Column('beta_fx', sa.Float(), nullable=True),
        sa.Column('average_daily_volume', sa.Float(), nullable=True),
        sa.Column('volatility_annualized', sa.Float(), nullable=True),
        sa.Column('base_spread', sa.Float(), nullable=True),
        sa.Column('updated_at', sa.DateTime()),
    )

    op.create_table(
        'covariance_matrices',
        sa.Column('matrix_type', sa.String(50), primary_key=True),
        sa.Column('tickers_list', sa.JSON()),
        sa.Column('data_matrix', sa.JSON()),
        sa.Column('updated_at', sa.DateTime()),
    )

    op.create_table(
        'stock_universe',
        sa.Column('ticker', sa.String(30), primary_key=True),
        sa.Column('company_name', sa.String(200), nullable=True),
        sa.Column('sector', sa.String(100), nullable=True),
        sa.Column('industry', sa.String(100), nullable=True),
        sa.Column('market_cap', sa.Float(), nullable=True),
        sa.Column('pe_ratio', sa.Float(), nullable=True),
        sa.Column('roe', sa.Float(), nullable=True),
        sa.Column('roce', sa.Float(), nullable=True),
        sa.Column('debt_to_equity', sa.Float(), nullable=True),
        sa.Column('promoter_holding', sa.Float(), nullable=True),
        sa.Column('fii_holding', sa.Float(), nullable=True),
        sa.Column('dii_holding', sa.Float(), nullable=True),
        sa.Column('dividend_yield', sa.Float(), nullable=True),
        sa.Column('ebitda_margin', sa.Float(), nullable=True),
        sa.Column('price_change_3m', sa.Float(), nullable=True),
        sa.Column('price_change_1y', sa.Float(), nullable=True),
        sa.Column('rsi', sa.Float(), nullable=True),
        sa.Column('updated_at', sa.DateTime()),
    )
    op.create_index('ix_stock_universe_market_cap', 'stock_universe', ['market_cap'], unique=False)
    op.create_index('ix_stock_universe_sector', 'stock_universe', ['sector'], unique=False)

    op.create_table(
        'alpha158_features',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('ticker', sa.String(30), nullable=False),
        sa.Column('date', sa.String(20), nullable=False),
        sa.Column('features', sa.JSON(), nullable=False),
        sa.Column('created_at', sa.DateTime()),
        sa.UniqueConstraint('ticker', 'date', name='uq_alpha158_ticker_date'),
    )
    op.create_index('ix_alpha158_features_ticker', 'alpha158_features', ['ticker'], unique=False)
    op.create_index('ix_alpha158_features_date', 'alpha158_features', ['date'], unique=False)

    op.create_table(
        'alpha158_features_normalized',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('ticker', sa.String(30), nullable=False),
        sa.Column('date', sa.String(20), nullable=False),
        sa.Column('feature_name', sa.String(30), nullable=False),
        sa.Column('feature_value', sa.Float(), nullable=False),
        sa.Column('computed_at', sa.DateTime()),
        sa.UniqueConstraint('ticker', 'date', 'feature_name', name='uq_alpha158_norm_ticker_date_feature'),
    )
    op.create_index('ix_alpha158_features_normalized_ticker', 'alpha158_features_normalized', ['ticker'], unique=False)
    op.create_index('ix_alpha158_features_normalized_date', 'alpha158_features_normalized', ['date'], unique=False)
    op.create_index('ix_alpha158_norm_ticker_date', 'alpha158_features_normalized', ['ticker', 'date'], unique=False)
    op.create_index('ix_alpha158_norm_feature_name', 'alpha158_features_normalized', ['feature_name'], unique=False)

    op.create_table(
        'analysis_predictions',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('analysis_history_id', sa.Integer(), sa.ForeignKey('analysis_history.id'), nullable=True),
        sa.Column('symbol', sa.String(30), nullable=False),
        sa.Column('created_at', sa.DateTime()),
        sa.Column('horizon_days', sa.Integer(), nullable=False),
        sa.Column('recommendation', sa.String(20), nullable=False),
        sa.Column('confidence_pct', sa.Integer(), nullable=False),
        sa.Column('llm_confidence', sa.Float(), nullable=True),
        sa.Column('quant_confidence', sa.Float(), nullable=True),
        sa.Column('ml_confidence', sa.Float(), nullable=True),
        sa.Column('venn_abers_confidence', sa.Float(), nullable=True),
        sa.Column('signal_agreement', sa.Float(), nullable=True),
        sa.Column('ml_engine_mode', sa.String(50), nullable=True),
        sa.Column('model_version', sa.String(50), nullable=True),
        sa.Column('scan_type', sa.String(50), nullable=True),
        sa.Column('regime_id', sa.String(50), nullable=True),
        sa.Column('entry_price', sa.Float(), nullable=True),
        sa.Column('target_price', sa.Float(), nullable=True),
        sa.Column('actual_return_7d', sa.Float(), nullable=True),
        sa.Column('actual_return_30d', sa.Float(), nullable=True),
        sa.Column('actual_return_90d', sa.Float(), nullable=True),
        sa.Column('hit_direction_7d', sa.Boolean(), nullable=True),
        sa.Column('hit_direction_30d', sa.Boolean(), nullable=True),
        sa.Column('hit_direction_90d', sa.Boolean(), nullable=True),
        sa.Column('brier_score_7d', sa.Float(), nullable=True),
        sa.Column('brier_score_30d', sa.Float(), nullable=True),
        sa.Column('brier_score_90d', sa.Float(), nullable=True),
    )
    op.create_index('ix_analysis_predictions_analysis_history_id', 'analysis_predictions', ['analysis_history_id'], unique=False)
    op.create_index('ix_analysis_predictions_symbol', 'analysis_predictions', ['symbol'], unique=False)
    op.create_index('ix_analysis_predictions_created_at', 'analysis_predictions', ['created_at'], unique=False)
    op.create_index('ix_ap_symbol_created', 'analysis_predictions', ['symbol', 'created_at'], unique=False)
    op.create_index('ix_ap_model_version', 'analysis_predictions', ['model_version'], unique=False)

    op.create_table(
        'company_financials',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('ticker', sa.String(30), nullable=False),
        sa.Column('period', sa.String(20), nullable=False),
        sa.Column('revenue', sa.Float(), nullable=True),
        sa.Column('net_income', sa.Float(), nullable=True),
        sa.Column('eps', sa.Float(), nullable=True),
        sa.Column('operating_margin', sa.Float(), nullable=True),
        sa.Column('free_cash_flow', sa.Float(), nullable=True),
        sa.Column('created_at', sa.DateTime()),
    )
    op.create_index('ix_company_financials_id', 'company_financials', ['id'], unique=False)
    op.create_index('ix_company_financials_ticker', 'company_financials', ['ticker'], unique=False)

    op.create_table(
        'shareholding_patterns',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('ticker', sa.String(30), nullable=False),
        sa.Column('quarter', sa.String(20), nullable=False),
        sa.Column('promoter_pct', sa.Float(), nullable=True),
        sa.Column('fii_pct', sa.Float(), nullable=True),
        sa.Column('dii_pct', sa.Float(), nullable=True),
        sa.Column('public_pct', sa.Float(), nullable=True),
        sa.Column('pledged_pct', sa.Float(), nullable=True),
        sa.Column('created_at', sa.DateTime()),
    )
    op.create_index('ix_shareholding_patterns_id', 'shareholding_patterns', ['id'], unique=False)
    op.create_index('ix_shareholding_patterns_ticker', 'shareholding_patterns', ['ticker'], unique=False)

    op.create_table(
        'corporate_actions',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('ticker', sa.String(30), nullable=False),
        sa.Column('ex_date', sa.String(20), nullable=False),
        sa.Column('record_date', sa.String(20), nullable=True),
        sa.Column('purpose', sa.String(200), nullable=False),
        sa.Column('dividend_amount', sa.Float(), nullable=True),
        sa.Column('created_at', sa.DateTime()),
    )
    op.create_index('ix_corporate_actions_id', 'corporate_actions', ['id'], unique=False)
    op.create_index('ix_corporate_actions_ticker', 'corporate_actions', ['ticker'], unique=False)

    op.create_table(
        'company_valuations',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('ticker', sa.String(30), nullable=False),
        sa.Column('date', sa.String(20), nullable=False),
        sa.Column('current_pe', sa.Float(), nullable=True),
        sa.Column('forward_pe', sa.Float(), nullable=True),
        sa.Column('pb_ratio', sa.Float(), nullable=True),
        sa.Column('ev_ebitda', sa.Float(), nullable=True),
        sa.Column('market_cap', sa.Float(), nullable=True),
        sa.Column('created_at', sa.DateTime()),
    )
    op.create_index('ix_company_valuations_id', 'company_valuations', ['id'], unique=False)
    op.create_index('ix_company_valuations_ticker', 'company_valuations', ['ticker'], unique=False)

    op.create_table(
        'risk_signals',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('ticker', sa.String(30), nullable=False),
        sa.Column('date', sa.String(20), nullable=False),
        sa.Column('signal_type', sa.String(50), nullable=False),
        sa.Column('severity', sa.String(20), nullable=False),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime()),
    )
    op.create_index('ix_risk_signals_id', 'risk_signals', ['id'], unique=False)
    op.create_index('ix_risk_signals_ticker', 'risk_signals', ['ticker'], unique=False)

    op.create_table(
        'youtube_video_summaries',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('video_id', sa.String(20), nullable=False),
        sa.Column('url', sa.Text(), nullable=False),
        sa.Column('title', sa.Text()),
        sa.Column('channel', sa.Text()),
        sa.Column('duration_seconds', sa.Integer()),
        sa.Column('transcript_hash', sa.String(64)),
        sa.Column('transcript_source', sa.String(50)),
        sa.Column('summary_provider', sa.String(50)),
        sa.Column('summary_json', sa.Text()),
        sa.Column('timestamps_json', sa.Text()),
        sa.Column('raw_transcript_preview', sa.Text()),
        sa.Column('estimated_input_tokens', sa.Integer()),
        sa.Column('estimated_output_tokens', sa.Integer()),
        sa.Column('created_at', sa.DateTime()),
        sa.Column('updated_at', sa.DateTime()),
        sa.Column('last_accessed_at', sa.DateTime(), nullable=True),
    )
    op.create_index('ix_youtube_video_summaries_id', 'youtube_video_summaries', ['id'], unique=False)
    op.create_index('ix_youtube_video_summaries_video_id', 'youtube_video_summaries', ['video_id'], unique=True)

    op.create_table(
        'user_preferences',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('theme', sa.String(50)),
        sa.Column('alerts_enabled', sa.Boolean()),
        sa.Column('created_at', sa.DateTime()),
        sa.Column('updated_at', sa.DateTime()),
    )
    op.create_index('ix_user_preferences_id', 'user_preferences', ['id'], unique=False)
    op.create_index('ix_user_preferences_user_id', 'user_preferences', ['user_id'], unique=True)

    op.create_table(
        'user_subscriptions',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('tier', sa.String(20), server_default='free', nullable=False),
        sa.Column('billing_cycle', sa.String(20), nullable=True),
        sa.Column('started_at', sa.DateTime(), nullable=True),
        sa.Column('renews_at', sa.DateTime(), nullable=True),
        sa.Column('is_active', sa.Boolean(), server_default='1', nullable=False),
        sa.Column('cancelled_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime()),
        sa.Column('updated_at', sa.DateTime()),
        sa.CheckConstraint("tier IN ('free','pro','super_pro')", name='ck_user_subscription_tier'),
        sa.CheckConstraint("billing_cycle IN ('monthly','annual') OR billing_cycle IS NULL", name='ck_user_subscription_billing_cycle'),
    )
    op.create_index('ix_user_subscriptions_id', 'user_subscriptions', ['id'], unique=False)
    op.create_index('ix_user_subscriptions_user_id', 'user_subscriptions', ['user_id'], unique=True)

    op.create_table(
        'in_app_notifications',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('type', sa.String(50), nullable=False),
        sa.Column('title', sa.String(200), nullable=False),
        sa.Column('body', sa.Text(), nullable=False),
        sa.Column('is_read', sa.Boolean()),
        sa.Column('action_url', sa.String(500), nullable=True),
        sa.Column('created_at', sa.DateTime()),
    )
    op.create_index('ix_in_app_notifications_id', 'in_app_notifications', ['id'], unique=False)
    op.create_index('ix_in_app_notifications_user_id', 'in_app_notifications', ['user_id'], unique=False)

    op.create_table(
        'watchlists',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('ticker', sa.String(30), nullable=False),
        sa.Column('added_at', sa.DateTime()),
    )
    op.create_index('ix_watchlists_id', 'watchlists', ['id'], unique=False)
    op.create_index('ix_watchlists_user_id', 'watchlists', ['user_id'], unique=False)
    op.create_index('ix_watchlists_ticker', 'watchlists', ['ticker'], unique=False)

    op.create_table(
        'mutual_funds',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('fund_name', sa.String(200), nullable=False),
        sa.Column('amc', sa.String(100), nullable=False),
        sa.Column('category', sa.String(50), nullable=False),
        sa.Column('scheme_code', sa.String(30), nullable=True),
        sa.Column('scheme_name', sa.String(200), nullable=True),
        sa.Column('amc_name', sa.String(100), nullable=True),
        sa.Column('sub_category', sa.String(50), nullable=True),
        sa.Column('nav', sa.Float(), nullable=True),
        sa.Column('nav_date', sa.String(20), nullable=True),
        sa.Column('aum_cr', sa.Float(), nullable=True),
        sa.Column('expense_ratio', sa.Float(), nullable=True),
        sa.Column('returns_1y', sa.Float(), nullable=True),
        sa.Column('returns_3y', sa.Float(), nullable=True),
        sa.Column('returns_5y', sa.Float(), nullable=True),
        sa.Column('risk_level', sa.String(20), nullable=True),
        sa.Column('fund_manager', sa.String(100), nullable=True),
        sa.Column('is_direct_plan', sa.Boolean(), nullable=True),
        sa.Column('is_growth_plan', sa.Boolean(), nullable=True),
        sa.Column('created_at', sa.DateTime()),
        sa.Column('updated_at', sa.DateTime()),
    )
    op.create_index('ix_mutual_funds_id', 'mutual_funds', ['id'], unique=False)
    op.create_index('ix_mutual_funds_fund_name', 'mutual_funds', ['fund_name'], unique=False)
    op.create_index('ix_mutual_funds_scheme_code', 'mutual_funds', ['scheme_code'], unique=True)
    op.create_index('ix_mutual_funds_scheme_name', 'mutual_funds', ['scheme_name'], unique=False)

    op.create_table(
        'ipo_listings',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('company_name', sa.String(200), nullable=False),
        sa.Column('symbol', sa.String(30), nullable=True),
        sa.Column('issue_price_min', sa.Float(), nullable=True),
        sa.Column('issue_price_max', sa.Float(), nullable=True),
        sa.Column('subscription_status', sa.Text(), nullable=True),
        sa.Column('price_band_low', sa.Float(), nullable=True),
        sa.Column('price_band_high', sa.Float(), nullable=True),
        sa.Column('lot_size', sa.Integer(), nullable=True),
        sa.Column('issue_size_cr', sa.Float(), nullable=True),
        sa.Column('open_date', sa.String(20), nullable=True),
        sa.Column('close_date', sa.String(20), nullable=True),
        sa.Column('listing_date', sa.String(20), nullable=True),
        sa.Column('status', sa.String(20), nullable=True),
        sa.Column('subscription_qib', sa.Float(), nullable=True),
        sa.Column('subscription_nii', sa.Float(), nullable=True),
        sa.Column('subscription_retail', sa.Float(), nullable=True),
        sa.Column('gmp', sa.Float(), nullable=True),
        sa.Column('created_at', sa.DateTime()),
        sa.Column('updated_at', sa.DateTime()),
    )
    op.create_index('ix_ipo_listings_id', 'ipo_listings', ['id'], unique=False)
    op.create_index('ix_ipo_listings_company_name', 'ipo_listings', ['company_name'], unique=False)
    op.create_index('ix_ipo_listings_symbol', 'ipo_listings', ['symbol'], unique=False)
    op.create_index('ix_ipo_listings_status', 'ipo_listings', ['status'], unique=False)

    op.create_table(
        'forum_boards',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('slug', sa.String(60), nullable=False),
        sa.Column('name', sa.String(150), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('board_type', sa.String(20), nullable=False),
        sa.Column('ticker', sa.String(30), nullable=True),
        sa.Column('created_at', sa.DateTime()),
    )
    op.create_index('ix_forum_boards_id', 'forum_boards', ['id'], unique=False)
    op.create_index('ix_forum_boards_slug', 'forum_boards', ['slug'], unique=True)
    op.create_index('ix_forum_boards_ticker', 'forum_boards', ['ticker'], unique=False)

    op.create_table(
        'forum_threads',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('board_id', sa.Integer(), sa.ForeignKey('forum_boards.id'), nullable=False),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('title', sa.String(200), nullable=False),
        sa.Column('is_pinned', sa.Boolean(), server_default='0', nullable=False),
        sa.Column('created_at', sa.DateTime()),
        sa.Column('updated_at', sa.DateTime()),
    )
    op.create_index('ix_forum_threads_id', 'forum_threads', ['id'], unique=False)
    op.create_index('ix_forum_threads_board_id', 'forum_threads', ['board_id'], unique=False)
    op.create_index('ix_forum_threads_user_id', 'forum_threads', ['user_id'], unique=False)

    op.create_table(
        'forum_posts',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('thread_id', sa.Integer(), sa.ForeignKey('forum_threads.id'), nullable=False),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('parent_post_id', sa.Integer(), sa.ForeignKey('forum_posts.id'), nullable=True),
        sa.Column('body', sa.Text(), nullable=False),
        sa.Column('is_op', sa.Boolean(), server_default='0', nullable=False),
        sa.Column('upvotes', sa.Integer(), server_default='0', nullable=False),
        sa.Column('downvotes', sa.Integer(), server_default='0', nullable=False),
        sa.Column('moderation_action', sa.String(10), server_default='allow', nullable=False),
        sa.Column('spam_score', sa.Integer(), nullable=True),
        sa.Column('sentiment', sa.String(10), nullable=True),
        sa.Column('created_at', sa.DateTime()),
    )
    op.create_index('ix_forum_posts_id', 'forum_posts', ['id'], unique=False)
    op.create_index('ix_forum_posts_thread_id', 'forum_posts', ['thread_id'], unique=False)
    op.create_index('ix_forum_posts_user_id', 'forum_posts', ['user_id'], unique=False)
    op.create_index('ix_forum_posts_parent_post_id', 'forum_posts', ['parent_post_id'], unique=False)

    op.create_table(
        'forum_polls',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('thread_id', sa.Integer(), sa.ForeignKey('forum_threads.id'), nullable=False),
        sa.Column('question', sa.String(300), nullable=False),
        sa.Column('created_at', sa.DateTime()),
    )
    op.create_index('ix_forum_polls_id', 'forum_polls', ['id'], unique=False)
    op.create_index('ix_forum_polls_thread_id', 'forum_polls', ['thread_id'], unique=True)

    op.create_table(
        'forum_poll_options',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('poll_id', sa.Integer(), sa.ForeignKey('forum_polls.id'), nullable=False),
        sa.Column('option_text', sa.String(150), nullable=False),
        sa.Column('vote_count', sa.Integer(), server_default='0', nullable=False),
    )
    op.create_index('ix_forum_poll_options_id', 'forum_poll_options', ['id'], unique=False)
    op.create_index('ix_forum_poll_options_poll_id', 'forum_poll_options', ['poll_id'], unique=False)

    op.create_table(
        'forum_votes',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('post_id', sa.Integer(), sa.ForeignKey('forum_posts.id'), nullable=True),
        sa.Column('poll_id', sa.Integer(), sa.ForeignKey('forum_polls.id'), nullable=True),
        sa.Column('poll_option_id', sa.Integer(), sa.ForeignKey('forum_poll_options.id'), nullable=True),
        sa.Column('vote_value', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime()),
        sa.UniqueConstraint('user_id', 'post_id', name='uq_forum_vote_user_post'),
        sa.UniqueConstraint('user_id', 'poll_id', name='uq_forum_vote_user_poll'),
    )
    op.create_index('ix_forum_votes_id', 'forum_votes', ['id'], unique=False)
    op.create_index('ix_forum_votes_user_id', 'forum_votes', ['user_id'], unique=False)
    op.create_index('ix_forum_votes_post_id', 'forum_votes', ['post_id'], unique=False)
    op.create_index('ix_forum_votes_poll_id', 'forum_votes', ['poll_id'], unique=False)
    op.create_index('ix_forum_votes_poll_option_id', 'forum_votes', ['poll_option_id'], unique=False)

    op.create_table(
        'kyc_consents',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('consent_type', sa.String(40), nullable=False),
        sa.Column('granted', sa.Boolean(), server_default='0', nullable=False),
        sa.Column('granted_at', sa.DateTime()),
        sa.Column('ip_address', sa.String(64), nullable=True),
        sa.Column('revoked_at', sa.DateTime(), nullable=True),
    )
    op.create_index('ix_kyc_consents_id', 'kyc_consents', ['id'], unique=False)
    op.create_index('ix_kyc_consents_user_id', 'kyc_consents', ['user_id'], unique=False)
    op.create_index('ix_kyc_consents_consent_type', 'kyc_consents', ['consent_type'], unique=False)

    op.create_table(
        'device_bindings',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('device_id', sa.String(120), nullable=False),
        sa.Column('bound_at', sa.DateTime()),
        sa.Column('is_primary', sa.Boolean(), server_default='1', nullable=False),
    )
    op.create_index('ix_device_bindings_id', 'device_bindings', ['id'], unique=False)
    op.create_index('ix_device_bindings_user_id', 'device_bindings', ['user_id'], unique=False)
    op.create_index('ix_device_bindings_device_id', 'device_bindings', ['device_id'], unique=False)

    op.create_table(
        'device_binding_attempts',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('device_id', sa.String(120), nullable=False),
        sa.Column('attempted_at', sa.DateTime()),
        sa.Column('outcome', sa.String(30), nullable=False),
        sa.Column('reason', sa.Text(), nullable=True),
        sa.UniqueConstraint('user_id', 'device_id', name='uq_device_binding_user_device'),
    )
    op.create_index('ix_device_binding_attempts_id', 'device_binding_attempts', ['id'], unique=False)
    op.create_index('ix_device_binding_attempts_user_id', 'device_binding_attempts', ['user_id'], unique=False)
    op.create_index('ix_device_binding_attempts_device_id', 'device_binding_attempts', ['device_id'], unique=False)
    op.create_index('ix_device_binding_attempts_attempted_at', 'device_binding_attempts', ['attempted_at'], unique=False)

    op.create_table(
        'linked_bank_accounts',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('bank_name', sa.String(100), nullable=False),
        sa.Column('account_type', sa.String(20), server_default='savings', nullable=False),
        sa.Column('masked_account_number', sa.String(20), nullable=False),
        sa.Column('ifsc_code', sa.String(15), nullable=True),
        sa.Column('is_primary', sa.Boolean(), server_default='1', nullable=False),
        sa.Column('linked_at', sa.DateTime()),
        sa.UniqueConstraint('user_id', 'masked_account_number', name='uq_linked_bank_account_user_number'),
    )
    op.create_index('ix_linked_bank_accounts_id', 'linked_bank_accounts', ['id'], unique=False)
    op.create_index('ix_linked_bank_accounts_user_id', 'linked_bank_accounts', ['user_id'], unique=False)

    op.create_table(
        'loan_offers',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('nbfc_name', sa.String(100), nullable=False),
        sa.Column('loan_type', sa.String(20), nullable=False),
        sa.Column('min_amount', sa.Numeric(14, 2), nullable=False),
        sa.Column('max_amount', sa.Numeric(14, 2), nullable=False),
        sa.Column('interest_rate_pct', sa.Numeric(5, 2), nullable=False),
        sa.Column('min_tenure_months', sa.Integer(), nullable=False),
        sa.Column('max_tenure_months', sa.Integer(), nullable=False),
        sa.Column('min_credit_score', sa.Integer(), server_default='650', nullable=False),
        sa.Column('processing_fee_pct', sa.Numeric(5, 2), server_default='1.0', nullable=False),
        sa.Column('is_active', sa.Boolean(), server_default='1', nullable=False),
        sa.Column('created_at', sa.DateTime()),
    )
    op.create_index('ix_loan_offers_id', 'loan_offers', ['id'], unique=False)
    op.create_index('ix_loan_offers_loan_type', 'loan_offers', ['loan_type'], unique=False)

    op.create_table(
        'loan_applications',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('loan_offer_id', sa.Integer(), sa.ForeignKey('loan_offers.id'), nullable=False),
        sa.Column('requested_amount', sa.Numeric(14, 2), nullable=False),
        sa.Column('requested_tenure_months', sa.Integer(), nullable=False),
        sa.Column('status', sa.String(20), server_default='submitted', nullable=False),
        sa.Column('mock_credit_score_at_application', sa.Integer(), nullable=True),
        sa.Column('decision_reason', sa.Text(), nullable=True),
        sa.Column('submitted_at', sa.DateTime()),
        sa.Column('decided_at', sa.DateTime(), nullable=True),
        sa.CheckConstraint("status IN ('submitted','under_review','approved','rejected','disbursed')", name='ck_loan_application_status'),
    )
    op.create_index('ix_loan_applications_id', 'loan_applications', ['id'], unique=False)
    op.create_index('ix_loan_applications_user_id', 'loan_applications', ['user_id'], unique=False)
    op.create_index('ix_loan_applications_loan_offer_id', 'loan_applications', ['loan_offer_id'], unique=False)
    op.create_index('ix_loan_applications_status', 'loan_applications', ['status'], unique=False)

    op.create_table(
        'loan_disbursements',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('loan_application_id', sa.Integer(), sa.ForeignKey('loan_applications.id'), nullable=False),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('linked_bank_account_id', sa.Integer(), sa.ForeignKey('linked_bank_accounts.id'), nullable=True),
        sa.Column('nbfc_name', sa.String(100), nullable=False),
        sa.Column('disbursed_amount', sa.Numeric(14, 2), nullable=False),
        sa.Column('status', sa.String(20), server_default='completed', nullable=False),
        sa.Column('disbursed_at', sa.DateTime()),
        sa.Column('failure_reason', sa.Text(), nullable=True),
        sa.CheckConstraint("status IN ('pending','completed','failed')", name='ck_loan_disbursement_status'),
    )
    op.create_index('ix_loan_disbursements_id', 'loan_disbursements', ['id'], unique=False)
    op.create_index('ix_loan_disbursements_loan_application_id', 'loan_disbursements', ['loan_application_id'], unique=False)
    op.create_index('ix_loan_disbursements_user_id', 'loan_disbursements', ['user_id'], unique=False)
    op.create_index('ix_loan_disbursements_linked_bank_account_id', 'loan_disbursements', ['linked_bank_account_id'], unique=False)
    op.create_index('ix_loan_disbursements_status', 'loan_disbursements', ['status'], unique=False)

    op.create_table(
        'finance_tracker_accounts',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('bank_name', sa.String(100), nullable=False),
        sa.Column('account_type', sa.String(20), server_default='savings', nullable=False),
        sa.Column('masked_account_number', sa.String(20), nullable=False),
        sa.Column('balance', sa.Numeric(14, 2), server_default='0', nullable=False),
        sa.Column('last_synced_at', sa.DateTime(), nullable=True),
        sa.Column('is_mock', sa.Boolean(), server_default='1', nullable=False),
        sa.Column('created_at', sa.DateTime()),
        sa.CheckConstraint("account_type IN ('savings','current','credit_card','wallet')", name='ck_finance_tracker_account_type'),
    )
    op.create_index('ix_finance_tracker_accounts_id', 'finance_tracker_accounts', ['id'], unique=False)
    op.create_index('ix_finance_tracker_accounts_user_id', 'finance_tracker_accounts', ['user_id'], unique=False)

    op.create_table(
        'audit_log_entries',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('action', sa.String(60), nullable=False),
        sa.Column('details', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime()),
        sa.Column('ip_address', sa.String(64), nullable=True),
    )
    op.create_index('ix_audit_log_entries_id', 'audit_log_entries', ['id'], unique=False)
    op.create_index('ix_audit_log_entries_user_id', 'audit_log_entries', ['user_id'], unique=False)
    op.create_index('ix_audit_log_entries_action', 'audit_log_entries', ['action'], unique=False)
    op.create_index('ix_audit_log_entries_created_at', 'audit_log_entries', ['created_at'], unique=False)

    op.create_table(
        'data_deletion_requests',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('status', sa.String(20), server_default='pending', nullable=False),
        sa.Column('requested_at', sa.DateTime()),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.Column('reason', sa.Text(), nullable=True),
        sa.CheckConstraint("status IN ('pending','processing','completed','cancelled')", name='ck_data_deletion_request_status'),
    )
    op.create_index('ix_data_deletion_requests_id', 'data_deletion_requests', ['id'], unique=False)
    op.create_index('ix_data_deletion_requests_user_id', 'data_deletion_requests', ['user_id'], unique=False)
    op.create_index('ix_data_deletion_requests_status', 'data_deletion_requests', ['status'], unique=False)

    op.create_table(
        'fixed_deposit_schemes',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('issuer_name', sa.String(100), nullable=False),
        sa.Column('min_tenure_months', sa.Integer(), nullable=False),
        sa.Column('max_tenure_months', sa.Integer(), nullable=False),
        sa.Column('min_amount', sa.Numeric(14, 2), nullable=False),
        sa.Column('max_amount', sa.Numeric(14, 2), nullable=False),
        sa.Column('interest_rate_pct', sa.Numeric(5, 2), nullable=False),
        sa.Column('senior_citizen_bonus_pct', sa.Numeric(5, 2), server_default='0.50', nullable=False),
        sa.Column('is_active', sa.Boolean(), server_default='1', nullable=False),
        sa.Column('created_at', sa.DateTime()),
    )
    op.create_index('ix_fixed_deposit_schemes_id', 'fixed_deposit_schemes', ['id'], unique=False)

    op.create_table(
        'fixed_deposit_bookings',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('scheme_id', sa.Integer(), sa.ForeignKey('fixed_deposit_schemes.id'), nullable=False),
        sa.Column('principal_amount', sa.Numeric(14, 2), nullable=False),
        sa.Column('tenure_months', sa.Integer(), nullable=False),
        sa.Column('interest_rate_pct', sa.Numeric(5, 2), nullable=False),
        sa.Column('maturity_amount', sa.Numeric(14, 2), nullable=False),
        sa.Column('payment_method', sa.String(20), nullable=False),
        sa.Column('status', sa.String(20), server_default='confirmed', nullable=False),
        sa.Column('decision_reason', sa.Text(), nullable=True),
        sa.Column('booked_at', sa.DateTime()),
        sa.Column('matures_at', sa.DateTime(), nullable=True),
        sa.CheckConstraint("status IN ('pending','confirmed','failed')", name='ck_fixed_deposit_booking_status'),
        sa.CheckConstraint("payment_method IN ('upi','net_banking')", name='ck_fixed_deposit_booking_payment_method'),
    )
    op.create_index('ix_fixed_deposit_bookings_id', 'fixed_deposit_bookings', ['id'], unique=False)
    op.create_index('ix_fixed_deposit_bookings_user_id', 'fixed_deposit_bookings', ['user_id'], unique=False)
    op.create_index('ix_fixed_deposit_bookings_scheme_id', 'fixed_deposit_bookings', ['scheme_id'], unique=False)
    op.create_index('ix_fixed_deposit_bookings_status', 'fixed_deposit_bookings', ['status'], unique=False)

    op.create_table(
        'research_runs',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('run_uid', sa.String(40), nullable=True),
        sa.Column('kind', sa.String(16), nullable=False),
        sa.Column('market_date', sa.Date(), nullable=True),
        sa.Column('status', sa.String(16), nullable=False),
        sa.Column('stage', sa.String(40), nullable=True),
        sa.Column('counts_json', sa.JSON(none_as_null=True), nullable=True),
        sa.Column('error', sa.Text(), nullable=True),
        sa.Column('started_at', sa.DateTime(), nullable=False),
        sa.Column('finished_at', sa.DateTime(), nullable=True),
        sa.UniqueConstraint('run_uid', name='uq_research_runs_run_uid'),
        sa.CheckConstraint("kind IN ('nightly','outcomes','live_metrics')", name='ck_research_runs_kind'),
        sa.CheckConstraint("status IN ('running','ok','degraded','failed','skipped_holiday')", name='ck_research_runs_status'),
    )
    op.create_index('ix_research_runs_kind_market_date', 'research_runs', ['kind', 'market_date'], unique=False)

    op.create_table(
        'research_reports',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('report_uid', sa.String(36), nullable=False),
        sa.Column('symbol', sa.String(30), nullable=False),
        sa.Column('isin', sa.String(12), nullable=True),
        sa.Column('as_of_date', sa.Date(), nullable=False),
        sa.Column('engine_version', sa.String(40), nullable=False),
        sa.Column('procedure_id', sa.String(40), nullable=True),
        sa.Column('run_id', sa.Integer(), sa.ForeignKey('research_runs.id'), nullable=True),
        sa.Column('origin', sa.String(10), nullable=False),
        sa.Column('status', sa.String(10), nullable=False),
        sa.Column('in_universe', sa.Boolean(), nullable=False),
        sa.Column('requested_by_user_id', sa.Integer(), nullable=True),
        sa.Column('report_json', sa.JSON(), nullable=False),
        sa.Column('facts_hash', sa.String(64), nullable=True),
        sa.Column('narrative_json', sa.JSON(none_as_null=True), nullable=True),
        sa.Column('narrative_status', sa.String(16), nullable=True),
        sa.Column('narrative_attempts', sa.SmallInteger(), server_default='0', nullable=False),
        sa.Column('narrative_failures_json', sa.JSON(none_as_null=True), nullable=True),
        sa.Column('narrative_generated_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.UniqueConstraint('report_uid', name='uq_research_reports_report_uid'),
        sa.UniqueConstraint('symbol', 'as_of_date', 'engine_version', 'origin', name='uq_research_reports_symbol_date_engine_origin'),
        sa.CheckConstraint("origin IN ('nightly','on_demand')", name='ck_research_reports_origin'),
        sa.CheckConstraint("status IN ('ok','degraded')", name='ck_research_reports_status'),
        sa.CheckConstraint("narrative_status IN ('llm_validated','template')", name='ck_research_reports_narrative_status'),
    )
    op.create_index('ix_research_reports_symbol_as_of_date', 'research_reports', ['symbol', 'as_of_date'], unique=False)

    op.create_table(
        'research_predictions',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('report_id', sa.Integer(), sa.ForeignKey('research_reports.id', ondelete='SET NULL'), nullable=True),
        sa.Column('symbol', sa.String(30), nullable=False),
        sa.Column('isin', sa.String(12), nullable=True),
        sa.Column('as_of_date', sa.Date(), nullable=False),
        sa.Column('horizon_days', sa.SmallInteger(), nullable=False),
        sa.Column('procedure_id', sa.String(40), nullable=False),
        sa.Column('model_id', sa.String(80), nullable=False),
        sa.Column('manifest_sha256', sa.String(64), nullable=False),
        sa.Column('universe_id', sa.String(20), nullable=False),
        sa.Column('evidence_tier', sa.String(24), nullable=False),
        sa.Column('reason_codes', sa.JSON(none_as_null=True), nullable=True),
        sa.Column('score', sa.Float(), nullable=False),
        sa.Column('rank_pct', sa.Float(), nullable=False),
        sa.Column('bucket', sa.SmallInteger(), nullable=True),
        sa.Column('p_top_half', sa.Float(), nullable=True),
        sa.Column('entry_close', sa.Numeric(14, 4), nullable=False),
        sa.Column('feature_hash', sa.String(64), nullable=True),
        sa.Column('expected_maturity_date', sa.Date(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('outcome_status', sa.String(10), server_default='pending', nullable=False),
        sa.Column('void_reason', sa.String(40), nullable=True),
        sa.Column('realized_return_pct', sa.Float(), nullable=True),
        sa.Column('realized_excess_pp', sa.Float(), nullable=True),
        sa.Column('realized_top_half', sa.Boolean(), nullable=True),
        sa.Column('nifty50_return_pct', sa.Float(), nullable=True),
        sa.Column('stale_exit', sa.Boolean(), nullable=True),
        sa.Column('scored_at', sa.DateTime(), nullable=True),
        sa.Column('scorer_version', sa.String(20), nullable=True),
        sa.UniqueConstraint('report_id', 'horizon_days', name='uq_research_predictions_report_horizon'),
        sa.UniqueConstraint('symbol', 'as_of_date', 'horizon_days', 'model_id', name='uq_research_predictions_symbol_date_horizon_model'),
        sa.CheckConstraint('horizon_days IN (21,63)', name='ck_research_predictions_horizon'),
        sa.CheckConstraint("outcome_status IN ('pending','matured','void')", name='ck_research_predictions_outcome_status'),
    )
    op.create_index('ix_research_predictions_outcome_maturity', 'research_predictions', ['outcome_status', 'expected_maturity_date'], unique=False)
    op.create_index('ix_research_predictions_procedure_horizon_as_of', 'research_predictions', ['procedure_id', 'horizon_days', 'as_of_date'], unique=False)

    op.create_table(
        'research_live_metrics',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('procedure_id', sa.String(40), nullable=False),
        sa.Column('horizon_days', sa.SmallInteger(), nullable=False),
        sa.Column('computed_on', sa.Date(), nullable=False),
        sa.Column('live_status', sa.String(16), nullable=False),
        sa.Column('live_gate_passed', sa.Boolean(), nullable=False),
        sa.Column('matured_n', sa.Integer(), nullable=False),
        sa.Column('matured_dates', sa.Integer(), nullable=False),
        sa.Column('metrics_json', sa.JSON(), nullable=False),
        sa.Column('alarms_json', sa.JSON(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.UniqueConstraint('procedure_id', 'horizon_days', 'computed_on', name='uq_research_live_metrics_procedure_horizon_day'),
        sa.CheckConstraint("live_status IN ('collecting','ok','under_review')", name='ck_research_live_metrics_live_status'),
    )



def downgrade() -> None:
    """Refuse: downgrading the baseline would drop every table."""
    raise NotImplementedError("baseline revision cannot be downgraded")
