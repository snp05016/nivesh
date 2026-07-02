"""SQLAlchemy ORM model definitions for the Nivesh application."""

from datetime import datetime, timezone

from sqlalchemy import (
    Boolean, CheckConstraint, Column, DateTime, Float, Integer, JSON, Numeric, String, Text,
    ForeignKey, Index, UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, relationship


class Base(DeclarativeBase):
    pass


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

class User(Base):
    """Represents a user in the system."""
    __tablename__ = "users"

    id            = Column(Integer, primary_key=True, autoincrement=True)
    username      = Column(String(50), unique=True, nullable=False)
    password_hash = Column(String(64), nullable=False)
    display_name  = Column(String(100), nullable=False)
    created_at    = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    portfolio        = relationship("Portfolio",       back_populates="user", cascade="all, delete-orphan")
    analysis_history = relationship("AnalysisHistory", back_populates="user", cascade="all, delete-orphan")
    price_targets    = relationship("PriceTarget",     back_populates="user", cascade="all, delete-orphan")
    trade_journal    = relationship("TradeJournal",    back_populates="user", cascade="all, delete-orphan")
    device_tokens    = relationship("DeviceToken",     back_populates="user", cascade="all, delete-orphan")
    portfolio_valuation_history = relationship("PortfolioValuationHistory", back_populates="user", cascade="all, delete-orphan")
    net_worth_ledger            = relationship("NetWorthLedger",            back_populates="user", cascade="all, delete-orphan")
    earnings_alerts             = relationship("EarningsAlert",             back_populates="user", cascade="all, delete-orphan")
    analysis_jobs               = relationship("AnalysisJob",               back_populates="user", cascade="all, delete-orphan")
    multi_asset_transactions    = relationship("PortfolioTransaction",      back_populates="user", cascade="all, delete-orphan")


class Portfolio(Base):
    """Dual-purpose: group_name=holdings requires shares>0/buy_price>0 (API-enforced).
    group_name=watchlist uses shares=0/buy_price=0 as intentional sentinels.
    All holding queries MUST filter: Portfolio.group_name == 'holdings'.
    """
    __tablename__ = "portfolio"

    id           = Column(Integer, primary_key=True, autoincrement=True)
    user_id      = Column(Integer, ForeignKey("users.id"), nullable=False)
    ticker       = Column(String(30), nullable=False)
    company_name = Column(String(200), nullable=False)
    shares       = Column(Float, nullable=False)
    buy_price     = Column(Float, nullable=False)
    target_price  = Column(Float, nullable=True)
    purchase_date = Column(String, nullable=True)
    group_name    = Column(String(50), default="watchlist")
    notes         = Column(Text, default="")
    is_virtual    = Column(Boolean, default=False, nullable=False, server_default="0")
    created_at    = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    group_id      = Column(Integer, ForeignKey("portfolio_groups.id"), nullable=True)

    user = relationship("User", back_populates="portfolio")

    __table_args__ = (
        Index("ix_portfolio_user_id", "user_id"),
        Index("ix_portfolio_user_ticker", "user_id", "ticker"),
        Index("ix_portfolio_group", "user_id", "group_name"),
        Index("ix_portfolio_group_id", "group_id"),
        UniqueConstraint("user_id", "ticker", "group_name", name="uq_portfolio_user_ticker_group"),
        CheckConstraint("group_name = 'watchlist' OR shares > 0", name="ck_portfolio_shares_positive"),
        CheckConstraint("group_name = 'watchlist' OR buy_price > 0", name="ck_portfolio_buy_price_positive"),
    )


class PortfolioGroup(Base):
    """Named groupings of portfolio positions (e.g. 'Core Holdings', 'Speculative')."""
    __tablename__ = "portfolio_groups"

    id         = Column(Integer, primary_key=True, autoincrement=True)
    user_id    = Column(Integer, ForeignKey("users.id"), nullable=False)
    name       = Column(String(200), default="Core Holdings")
    is_default = Column(Boolean, default=True, server_default="1")
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        Index("ix_portfolio_groups_user_id", "user_id"),
    )


class Transaction(Base):
    """Immutable ledger of all portfolio transactions (BUY, SELL, SPLIT, BONUS, DIVIDEND)."""
    __tablename__ = "portfolio_transactions"

    id               = Column(Integer, primary_key=True, autoincrement=True)
    user_id          = Column(Integer, ForeignKey("users.id"), nullable=False)
    group_id         = Column(Integer, ForeignKey("portfolio_groups.id"), nullable=True)
    ticker           = Column(String(30), nullable=False)
    transaction_type = Column(String(20), nullable=False)  # BUY, SELL, SPLIT, BONUS, DIVIDEND
    quantity         = Column(Float, nullable=False)
    price            = Column(Float, nullable=False)
    fees             = Column(Float, default=0.0, server_default="0.0")
    date             = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    notes            = Column(String(500), nullable=True)
    created_at       = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        Index("ix_portfolio_transactions_user_id", "user_id"),
        Index("ix_portfolio_transactions_ticker", "ticker"),
        Index("ix_portfolio_transactions_group_id", "group_id"),
        Index("ix_portfolio_transactions_date", "date"),
    )


class PortfolioTransaction(Base):
    """Immutable ledger of multi-asset portfolio transactions (Stocks, MFs, Gold, FDs)."""
    __tablename__ = "multi_asset_transactions"

    id               = Column(Integer, primary_key=True, autoincrement=True)
    user_id          = Column(Integer, ForeignKey("users.id"), nullable=False)
    asset_type       = Column(String(20), nullable=False)  # STOCK, MF, GOLD, FD
    symbol           = Column(String(50), nullable=False)  # Ticker, ISIN, or account
    transaction_type = Column(String(20), nullable=False)  # BUY, SELL, DEPOSIT, WITHDRAWAL, MATURITY
    quantity         = Column(Float, nullable=False)
    price            = Column(Float, nullable=False)
    fees             = Column(Float, default=0.0, server_default="0.0")
    date             = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    notes            = Column(String(500), nullable=True)
    created_at       = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    user = relationship("User", back_populates="multi_asset_transactions")

    __table_args__ = (
        Index("ix_multi_asset_transactions_user_id", "user_id"),
        Index("ix_multi_asset_transactions_asset_type", "asset_type"),
        Index("ix_multi_asset_transactions_symbol", "symbol"),
        Index("ix_multi_asset_transactions_date", "date"),
    )


class AnalysisHistory(Base):
    """Records historical stock analysis results."""
    __tablename__ = "analysis_history"

    id             = Column(Integer, primary_key=True, autoincrement=True)
    user_id        = Column(Integer, ForeignKey("users.id"), nullable=True)
    ticker         = Column(String(30), nullable=False)
    analysis_date  = Column(String(20), nullable=False)
    signal         = Column(String(20), nullable=False)
    confidence_pct = Column(Integer, nullable=True)
    target_short   = Column(Float, nullable=True)
    target_medium  = Column(Float, nullable=True)
    target_long    = Column(Float, nullable=True)
    promoter_pledged_pct = Column(Float, nullable=True)
    promoter_pledged_trend = Column(String(20), nullable=True)
    raw_output     = Column(Text, nullable=True)
    full_json      = Column(Text, nullable=False)
    scan_type      = Column(String(20), nullable=False, default="standard")
    # Epistemic feedback loop — added 2026-06-03
    outcome_delta_pct    = Column(Float, nullable=True)   # % price change since analysis
    was_correct          = Column(Boolean, nullable=True)  # signal matched price direction
    outcome_checked_at   = Column(DateTime, nullable=True)
    # ML Hybrid Pipeline — quantitative engine columns (added 2026-06-14)
    market_regime               = Column(String, nullable=True)
    calibrated_confidence        = Column(Float, nullable=True, default=0.0, server_default="0.0")
    confidence_math_breakdown   = Column(JSON, default="{}")
    conformal_target_upper_3m   = Column(Float, nullable=True)
    conformal_target_lower_3m   = Column(Float, nullable=True)
    quantitative_drivers        = Column(JSON, default="{}")
    tail_risk_flags             = Column(JSON, default="{}")
    created_at     = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    user = relationship("User", back_populates="analysis_history")

    __table_args__ = (
        Index("ix_analysis_history_user_id", "user_id"),
        Index("ix_analysis_history_ticker", "ticker"),
        Index("ix_analysis_history_scan_type", "scan_type"),
        Index("ix_analysis_history_created_at", "created_at"),
        Index("ix_analysis_history_ticker_user", "ticker", "user_id"),
    )


class SignalEvent(Base):
    """Records transitions between trading signals."""
    __tablename__ = "signal_events"
    id          = Column(Integer, primary_key=True, autoincrement=True)
    ticker      = Column(String(20), nullable=False, index=True)
    from_signal = Column(String(30), nullable=False)
    to_signal   = Column(String(30), nullable=False)
    event_date  = Column(String(20), nullable=False)
    created_at  = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class AnalysisJob(Base):
    """Server-side background analysis job — the single source of truth for
    'is an analysis running?'. Decoupled from the HTTP connection (v2 engine)."""
    __tablename__ = "analysis_jobs"

    job_id       = Column(String(12), primary_key=True)
    user_id      = Column(Integer, ForeignKey("users.id"), nullable=True)
    ticker       = Column(String(30), nullable=False)
    exchange     = Column(String(10), nullable=False, default="NSE")
    scan_type    = Column(String(20), nullable=False, default="standard")
    status       = Column(String(20), nullable=False, default="QUEUED")   # QUEUED/RUNNING/SUCCEEDED/FAILED/CANCELLED/TIMEOUT
    stage        = Column(String(60), nullable=True)
    progress_pct = Column(Integer, nullable=False, default=0)
    checkpoints  = Column(Text, nullable=False, default="[]")             # JSON list of {ts,stage,agent,message,state}
    pid          = Column(Integer, nullable=True)
    heartbeat_at = Column(DateTime, nullable=True)
    tokens_used  = Column(Integer, nullable=False, default=0)
    error        = Column(Text, nullable=True)
    result_json  = Column(Text, nullable=True)                            # full normalized result when SUCCEEDED
    created_at   = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    started_at   = Column(DateTime, nullable=True)
    finished_at  = Column(DateTime, nullable=True)

    user = relationship("User", back_populates="analysis_jobs")

    __table_args__ = (
        Index("ix_analysis_jobs_user_id", "user_id"),
        Index("ix_analysis_jobs_ticker", "ticker"),
    )


class PriceTarget(Base):
    """Stores user-defined price targets for stocks."""
    __tablename__ = "price_targets"

    id           = Column(Integer, primary_key=True, autoincrement=True)
    user_id      = Column(Integer, ForeignKey("users.id"), nullable=False)
    ticker       = Column(String(30), nullable=False)
    target_price = Column(Float, nullable=False)
    direction    = Column(String(10), nullable=False)
    triggered    = Column(Boolean, default=False)
    created_at   = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    user = relationship("User", back_populates="price_targets")

    __table_args__ = (
        Index("ix_price_targets_user_id", "user_id"),
        CheckConstraint("target_price > 0", name="ck_price_targets_positive"),
    )


class TradeJournal(Base):
    """Records user trading activities and reflections."""
    __tablename__ = "trade_journal"

    id             = Column(Integer, primary_key=True, autoincrement=True)
    user_id        = Column(Integer, ForeignKey("users.id"), nullable=False)
    ticker         = Column(String(30), nullable=False)
    action         = Column(String(10), nullable=False)  # BUY / SELL / HOLD / WATCH
    price_at_time  = Column(Float, nullable=False)
    reason_text    = Column(Text, nullable=False)
    outcome_text   = Column(Text, nullable=True)
    company_name   = Column(String(200), nullable=True)   # added — run migrate_trade_journal.py
    mood           = Column(String(30), nullable=True)    # added — run migrate_trade_journal.py
    updated_at     = Column(DateTime, nullable=True)      # added — run migrate_trade_journal.py
    is_virtual     = Column(Boolean, default=False, nullable=False, server_default="0")
    created_at     = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    user = relationship("User", back_populates="trade_journal")

    __table_args__ = (
        Index("ix_trade_journal_user_id", "user_id"),
    )


class DividendLedger(Base):
    """Tracks dividend income per ticker for tax-loss harvesting and income reporting."""
    __tablename__ = "dividend_ledger"

    id           = Column(Integer, primary_key=True, autoincrement=True)
    user_id      = Column(Integer, ForeignKey("users.id"), nullable=False)
    portfolio_id = Column(Integer, nullable=True)  # FK to portfolios removed until table exists
    ticker       = Column(String(30), nullable=False)
    amount       = Column(Float, nullable=False)
    ex_date      = Column(String(20), nullable=True)
    payment_date = Column(String(20), nullable=True)
    created_at   = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        Index("ix_dividend_ledger_user_ticker", "user_id", "ticker"),
    )


class TaxReport(Base):
    """Annual tax-loss harvesting snapshot per user, per financial year."""
    __tablename__ = "tax_reports"

    id         = Column(Integer, primary_key=True, autoincrement=True)
    user_id    = Column(Integer, ForeignKey("users.id"), nullable=False)
    fy_year    = Column(String(20), nullable=False)
    stcg       = Column(Float, default=0.0)
    ltcg       = Column(Float, default=0.0)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc),
                         onupdate=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        UniqueConstraint("user_id", "fy_year", name="uq_tax_report_user_fy"),
    )


class DeviceToken(Base):
    """Stores push notification device tokens for users."""
    __tablename__ = "device_tokens"

    id           = Column(Integer, primary_key=True, autoincrement=True)
    user_id      = Column(Integer, ForeignKey("users.id"), nullable=False)
    device_token = Column(String(200), unique=True, nullable=False)
    platform     = Column(String(10), default="ios")
    created_at   = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at   = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    user = relationship("User", back_populates="device_tokens")

    __table_args__ = (
        Index("ix_device_tokens_user_id", "user_id"),
    )


class AdvisorInsight(Base):
    """
    Stores structured stance data extracted from YouTube financial advisor videos.
    Populated exclusively by the nightly advisor_harvester.py CRON job.
    Never written to during live API request handling.
    """
    __tablename__ = "advisor_insights"

    id              = Column(Integer, primary_key=True, index=True)
    ticker          = Column(String, index=True, nullable=False)
    advisor_name    = Column(String, nullable=False)
    channel_id      = Column(String, nullable=False)
    video_id        = Column(String, nullable=False)
    video_title     = Column(String, nullable=False)
    video_url       = Column(String, nullable=False)
    published_at    = Column(DateTime, nullable=False)
    transcript_source = Column(String, nullable=False)
    stance          = Column(String, nullable=False)
    confidence      = Column(String, nullable=False)
    catalyst_summary = Column(String, nullable=False)
    raw_snippet     = Column(Text, nullable=True)
    view_count      = Column(Integer, default=0)
    created_at      = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        UniqueConstraint('video_id', 'ticker', name='uq_video_ticker'),
        Index('ix_advisor_ticker_published', 'ticker', 'published_at'),
    )


class NewsArticle(Base):
    """Stores financial news articles and AI sentiment summaries."""
    __tablename__ = "news_articles"

    id              = Column(Integer, primary_key=True, index=True)
    source          = Column(String, nullable=False)        # "moneycontrol" | "economic_times" | "nse"
    ticker          = Column(String, nullable=True, index=True)  # NULL if market-wide news
    headline        = Column(String, nullable=False)
    summary         = Column(Text, nullable=True)           # 2-3 sentence AI summary
    body_text       = Column(Text, nullable=True)           # Full article body (stripped HTML)
    image_url       = Column(String, nullable=True)
    article_url     = Column(String, nullable=False, unique=True)
    published_at    = Column(DateTime, nullable=False)
    sentiment       = Column(String, nullable=True)         # "POSITIVE" | "NEUTRAL" | "NEGATIVE"
    sentiment_score = Column(Float, nullable=True)          # FinBERT score: -1.0 to +1.0
    sentiment_label = Column(String, nullable=True)         # "Positive" | "Negative" | "Neutral"
    is_red_flag     = Column(Boolean, default=False)        # True if contains auditor/CFO/SEBI keywords
    created_at      = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class YouTubeVideo(Base):
    """Stores harvested financial YouTube video metadata."""
    __tablename__ = "youtube_videos"

    id              = Column(Integer, primary_key=True, index=True)
    video_id        = Column(String, nullable=False, unique=True)
    channel_name    = Column(String, nullable=False)
    title           = Column(String, nullable=False)
    description_snippet = Column(String, nullable=True)
    channel_url     = Column(String, nullable=True)
    thumbnail_url   = Column(String, nullable=True)
    video_url       = Column(String, nullable=False)
    published_at    = Column(DateTime, nullable=False)
    view_count      = Column(Integer, default=0)
    duration_seconds = Column(Integer, default=0)
    tickers_mentioned = Column(String, nullable=True)
    created_at      = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    harvested_at    = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    matched_ticker  = Column(String, nullable=True, index=True)
    source          = Column(String, default="channel_harvest")
    sebi_reg        = Column(String, nullable=True)


class PortfolioValuationHistory(Base):
    """Tracks historical portfolio valuations for users."""
    __tablename__ = "portfolio_valuation_history"

    id              = Column(Integer, primary_key=True, index=True)
    user_id         = Column(
        Integer,
        ForeignKey("users.id", name="fk_portfolio_valuation_history_user_id"),
        nullable=False,
        index=True,
    )
    snapshot_date   = Column(String, nullable=False)        # "2026-06-02" ISO date string
    total_value     = Column(Float, nullable=False)         # Total portfolio value in INR
    total_invested  = Column(Float, nullable=False)         # Total cost basis
    total_pnl       = Column(Float, nullable=False)         # total_value - total_invested
    pnl_percent     = Column(Float, nullable=False)         # (pnl / invested) * 100
    nifty_close     = Column(Float, nullable=True)          # NIFTY 50 close that day (for benchmark)
    created_at      = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    user = relationship("User", back_populates="portfolio_valuation_history")

    __table_args__ = (
        UniqueConstraint('user_id', 'snapshot_date', name='uq_user_date_snapshot'),
    )


class PKScreenerSignal(Base):
    """Records quantitative signals generated by PKScreener."""
    __tablename__ = "pkscreener_signals"

    id              = Column(Integer, primary_key=True, index=True)
    ticker          = Column(String, nullable=False, index=True)
    signal_date     = Column(String, nullable=False)               # "2026-06-02"
    screen_result   = Column(String, nullable=True)                # Raw PKScreener output
    breakout        = Column(Boolean, default=False)
    consolidating   = Column(Boolean, default=False)
    rsi             = Column(Float, nullable=True)
    macd_signal     = Column(String, nullable=True)                # "BUY" | "SELL" | "NEUTRAL"
    ma_signal       = Column(String, nullable=True)                # "Above50MA" | "Below200MA" etc.
    volume_signal   = Column(String, nullable=True)                # "HighVolume" | "Normal"
    pattern         = Column(String, nullable=True)                # "Bull Flag" | "Cup and Handle" etc.
    technical_score = Column(Float, nullable=True)                 # 0.0 = strong sell, 1.0 = strong buy
    created_at      = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        UniqueConstraint('ticker', 'signal_date', name='uq_ticker_date_signal'),
    )


class MacroEvent(Base):
    """Stores macroeconomic events and their outcomes."""
    __tablename__ = "macro_events"

    id              = Column(Integer, primary_key=True, index=True)
    title           = Column(String(300), nullable=False)
    event_date      = Column(String(20), nullable=False)           # "2026-06-04"
    event_time      = Column(String(10), nullable=True)            # "14:30" IST
    impact          = Column(String(10), nullable=False, default="MEDIUM")  # HIGH / MEDIUM / LOW
    consensus       = Column(String(100), nullable=True)           # e.g. "6.25%"
    actual          = Column(String(100), nullable=True)           # e.g. "6.50%" — filled post-release
    prior           = Column(String(100), nullable=True)           # previous reading
    category        = Column(String(50), nullable=True)            # MONETARY / FISCAL / EARNINGS / GLOBAL
    source          = Column(String(100), nullable=True)           # "RBI" / "SEBI" / "NSE"
    created_at      = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at      = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        Index("ix_macro_events_date", "event_date"),
    )


class NetWorthLedger(Base):
    """Tracks daily net worth summaries for users."""
    __tablename__ = "net_worth_ledger"

    id                   = Column(Integer, primary_key=True, index=True)
    user_id              = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    snapshot_date        = Column(String(20), nullable=False)      # "2026-06-04"
    total_value_inr      = Column(Float, nullable=False)           # absolute INR value
    daily_delta_inr      = Column(Float, nullable=True)            # change since previous day (INR)
    daily_delta_pct      = Column(Float, nullable=True)            # % change since previous day
    peak_value_inr       = Column(Float, nullable=True)            # all-time high
    top_gainer_ticker    = Column(String(30), nullable=True)       # best single-day performer
    top_gainer_pct       = Column(Float, nullable=True)            # its % gain
    top_loser_ticker     = Column(String(30), nullable=True)       # worst single-day performer
    top_loser_pct        = Column(Float, nullable=True)            # its % loss
    portfolio_json       = Column(Text, nullable=True)             # full breakdown JSON
    created_at           = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    user = relationship("User", foreign_keys=[user_id], back_populates="net_worth_ledger")

    __table_args__ = (
        UniqueConstraint("user_id", "snapshot_date", name="uq_networth_user_date"),
    )


class MarketErrorLog(Base):
    """Logs errors from background market data extraction tasks."""
    __tablename__ = "market_error_logs"

    id             = Column(Integer, primary_key=True, index=True)
    timestamp      = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    component      = Column(String(100), nullable=False)   # "filings_extractor", "nse_data_provider", etc.
    error_message  = Column(Text, nullable=False)            # full traceback / error string
    context_ticker = Column(String(30), nullable=True)       # optional — ticker being processed when error hit


def log_market_error(component: str, error_message: str, context_ticker: str | None = None) -> None:
    """Write a diagnostic error row to market_error_logs. Non-fatal — swallows its own errors."""
    from database import get_session
    try:
        with get_session() as session:
            entry = MarketErrorLog(
                component=component,
                error_message=str(error_message)[:2000],  # guard against runaway text
                context_ticker=context_ticker,
            )
            session.add(entry)
            session.commit()
    except Exception as _e:
        pass  # telemetry must never cause a cascading failure


class EarningsAlert(Base):
    """Stores user alerts for upcoming earnings announcements."""
    __tablename__ = "earnings_alerts"

    id            = Column(Integer, primary_key=True, index=True)
    user_id       = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    ticker        = Column(String(30), nullable=False)
    earnings_date = Column(String(20), nullable=False)          # "2026-06-15"
    created_at    = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    user = relationship("User", foreign_keys=[user_id], back_populates="earnings_alerts")

    __table_args__ = (
        UniqueConstraint("user_id", "ticker", "earnings_date", name="uq_user_ticker_earnings_date"),
    )


class EarningsErrorLog(Base):
    """Logs errors from the earnings tracking system."""
    __tablename__ = "earnings_error_logs"

    id             = Column(Integer, primary_key=True, index=True)
    timestamp      = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    module         = Column(String(100), nullable=False)   # "filings_extractor", "earnings_calendar", "earnings_feed"
    error_trace    = Column(Text, nullable=False)            # full traceback / error string
    failed_ticker  = Column(String(30), nullable=True)       # ticker being processed when error occurred


def log_earnings_error(module: str, error_trace: str, failed_ticker: str | None = None) -> None:
    """Write a diagnostic error row to earnings_error_logs. Non-fatal."""
    from database import get_session
    try:
        with get_session() as session:
            entry = EarningsErrorLog(
                module=module,
                error_trace=str(error_trace)[:2000],
                failed_ticker=failed_ticker,
            )
            session.add(entry)
            session.commit()
    except Exception as _e:
        pass  # telemetry must never cascade


class BlockDeal(Base):
    """Records large institutional block deals."""
    __tablename__ = "block_deals"

    id = Column(Integer, primary_key=True, index=True)
    date = Column(String(20), nullable=False, index=True)
    ticker = Column(String(30), nullable=False, index=True)
    client_name = Column(String(200), nullable=False)
    deal_type = Column(String(20), nullable=False) # "BUY" or "SELL"
    quantity = Column(Integer, nullable=False)
    price = Column(Float, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class FIIDIIFlow(Base):
    """Records daily FII and DII institutional flows."""
    __tablename__ = "fii_dii_flow"

    id = Column(Integer, primary_key=True, index=True)
    date = Column(String(20), nullable=False, unique=True, index=True)
    fii_buy = Column(Float, nullable=False)
    fii_sell = Column(Float, nullable=False)
    fii_net = Column(Float, nullable=False)
    dii_buy = Column(Float, nullable=False)
    dii_sell = Column(Float, nullable=False)
    dii_net = Column(Float, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class NotificationErrorLog(Base):
    """Logs errors from the push notification system."""
    __tablename__ = "notification_error_logs"

    id            = Column(Integer, primary_key=True, index=True)
    timestamp     = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    failure_point = Column(String(100), nullable=False)   # "token_registration", "apns_dispatch"
    error_trace   = Column(Text, nullable=False)            # full traceback / error string
    target_device = Column(String(200), nullable=True)      # device token or identifier


def log_notification_error(failure_point: str, error_trace: str, target_device: str | None = None) -> None:
    """Write a diagnostic error row to notification_error_logs. Non-fatal."""
    from database import get_session
    try:
        with get_session() as session:
            entry = NotificationErrorLog(
                failure_point=failure_point,
                error_trace=str(error_trace)[:2000],
                target_device=target_device,
            )
            session.add(entry)
            session.commit()
    except Exception as _e:
        pass  # telemetry must never cascade


class AdvisorBiography(Base):
    """Stores biographical information for financial advisors."""
    __tablename__ = "advisor_biographies"

    id = Column(Integer, primary_key=True, index=True)
    advisor_name = Column(String(100), nullable=False, index=True)
    sebi_reg_number = Column(String(20), nullable=False, unique=True)
    experience_years = Column(Integer, default=0)
    analytical_framework = Column(String(200), nullable=True)  # e.g. "Wyckoff, Volume Profile"
    full_biography_text = Column(Text, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class TextAdvisoryInsight(Base):
    """Stores textual insights and predictions from advisors."""
    __tablename__ = "text_advisory_insights"

    id = Column(Integer, primary_key=True, index=True)
    advisor_id = Column(Integer, ForeignKey("advisor_biographies.id"), nullable=False, index=True)
    timestamp = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    content_text = Column(Text, nullable=False)
    target_ticker = Column(String(30), nullable=True, index=True)
    extracted_sentiment = Column(String(20), nullable=True)  # BULLISH/BEARISH/NEUTRAL
    source_url = Column(String(500), nullable=True)

    advisor = relationship("AdvisorBiography", foreign_keys=[advisor_id])


class IdeasErrorLog(Base):
    """Logs errors from the ideas extraction module."""
    __tablename__ = "ideas_error_logs"

    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    module = Column(String(100), nullable=False)
    error_trace = Column(Text, nullable=False)
    context_ticker = Column(String(30), nullable=True)


def log_ideas_error(module: str, error_trace: str, context_ticker: str | None = None) -> None:
    """Write a diagnostic error row to ideas_error_logs. Non-fatal — swallows its own errors."""
    from database import get_session
    try:
        with get_session() as session:
            entry = IdeasErrorLog(
                module=module,
                error_trace=str(error_trace)[:2000],  # guard against runaway text
                context_ticker=context_ticker,
            )
            session.add(entry)
            session.commit()
    except Exception as _e:
        pass  # telemetry must never cause a cascading failure


class MarketAnomaly(Base):
    """Records detected market anomalies and unusual activities."""
    __tablename__ = "market_anomalies"
    id = Column(Integer, primary_key=True, index=True)
    ticker = Column(String)
    company = Column(String)
    anomaly_type = Column(String)
    severity = Column(String)
    detail = Column(Text)
    price = Column(Float)
    change_pct = Column(Float)
    timestamp = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        Index("ix_market_anomalies_anomaly_type", "anomaly_type"),
        Index("ix_market_anomalies_ticker", "ticker"),
        Index("ix_market_anomalies_timestamp", "timestamp"),
    )


class EarningsSurpriseHistory(Base):
    """Records historical earnings surprises vs estimates."""
    __tablename__ = "earnings_surprise_history"
    id = Column(Integer, primary_key=True, index=True)
    ticker = Column(String)
    company_name = Column(String)
    quarter = Column(String)
    estimated_eps = Column(Float)
    actual_eps = Column(Float)
    surprise_pct = Column(Float)
    classification = Column(String)
    post_price_1d = Column(Float)
    post_price_5d = Column(Float)
    historical_score = Column(Float)
    serial_pattern = Column(String)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        Index("ix_earnings_surprise_history_ticker", "ticker"),
    )


# ── Stress Test Engine Tables (Tier 2.5) ─────────────────────────────────

class EquityRiskFactor(Base):
    """Pre-calculated quantitative risk attributes for individual stocks. Updated nightly."""
    __tablename__ = "equity_risk_factors"
    ticker = Column(String(30), primary_key=True)
    beta_market = Column(Float, nullable=True, default=1.0)
    beta_oil = Column(Float, nullable=True, default=0.0)
    beta_rates = Column(Float, nullable=True, default=0.0)
    beta_fx = Column(Float, nullable=True, default=0.0)
    average_daily_volume = Column(Float, nullable=True, default=1e6)
    volatility_annualized = Column(Float, nullable=True, default=0.30)
    base_spread = Column(Float, nullable=True, default=0.005)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

class CovarianceMatrix(Base):
    """Serialized covariance matrices for stress testing. Prevents recomputation."""
    __tablename__ = "covariance_matrices"
    matrix_type = Column(String(50), primary_key=True)
    tickers_list = Column(JSON, default="[]")
    data_matrix = Column(JSON, default="[]")
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

class StockUniverse(Base):
    """Nightly cached fundamental data for 2000+ Indian stocks. Used by NL Screener."""
    __tablename__ = "stock_universe"
    
    ticker = Column(String(30), primary_key=True)
    company_name = Column(String(200), nullable=True)
    sector = Column(String(100), nullable=True)
    industry = Column(String(100), nullable=True)
    
    market_cap = Column(Float, nullable=True)          # Absolute INR
    pe_ratio = Column(Float, nullable=True)
    roe = Column(Float, nullable=True)                 # Percentage (e.g., 15.5 for 15.5%)
    roce = Column(Float, nullable=True)                # Percentage
    debt_to_equity = Column(Float, nullable=True)      # Ratio (e.g. 1.2)
    promoter_holding = Column(Float, nullable=True)    # Percentage
    fii_holding = Column(Float, nullable=True)         # Percentage
    dii_holding = Column(Float, nullable=True)         # Percentage
    dividend_yield = Column(Float, nullable=True)      # Percentage
    ebitda_margin = Column(Float, nullable=True)       # Percentage
    
    price_change_3m = Column(Float, nullable=True)     # Percentage
    price_change_1y = Column(Float, nullable=True)     # Percentage
    rsi = Column(Float, nullable=True)                 # 0-100
    
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        Index("ix_stock_universe_market_cap", "market_cap"),
        Index("ix_stock_universe_sector", "sector"),
    )


class Alpha158Feature(Base):
    """Nightly computed Alpha158 features for stock universe.
    Features dict maps feature name to scaled/unscaled float value.
    """
    __tablename__ = "alpha158_features"

    id = Column(Integer, primary_key=True, autoincrement=True)
    ticker = Column(String(30), nullable=False, index=True)
    date = Column(String(20), nullable=False, index=True)
    features = Column(JSON, nullable=False, default="{}")
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        UniqueConstraint("ticker", "date", name="uq_alpha158_ticker_date"),
    )


class Alpha158Features(Base):
    """Normalized (long-form) Alpha158 feature store — one row per (ticker, date, feature_name).

    Produced by the nightly Alpha158 materialization Celery task
    (backend/tasks/alpha158_task.py). Stored alongside the wide-JSON
    Alpha158Feature table: this table enables efficient per-feature
    queries and ML training set assembly without deserialising blobs.

    Point-in-Time safety: the ``date`` column records the T for which
    features were computed.  All upstream OHLCV data used to compute
    features for a given ``date`` must only include rows with
    trade_date <= T (enforced in alpha158_task.py).
    """
    __tablename__ = "alpha158_features_normalized"

    id           = Column(Integer, primary_key=True, autoincrement=True)
    ticker       = Column(String(30), nullable=False, index=True)
    date         = Column(String(20), nullable=False, index=True)   # ISO date string "YYYY-MM-DD"
    feature_name = Column(String(30), nullable=False)
    feature_value = Column(Float, nullable=False)
    computed_at  = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        UniqueConstraint(
            "ticker", "date", "feature_name",
            name="uq_alpha158_norm_ticker_date_feature",
        ),
        Index("ix_alpha158_norm_ticker_date", "ticker", "date"),
        Index("ix_alpha158_norm_feature_name", "feature_name"),
    )


class AnalysisPrediction(Base):
    """Stores machine learning and quantitative predictions for analysis jobs."""
    __tablename__ = "analysis_predictions"

    id                    = Column(Integer, primary_key=True, autoincrement=True)
    analysis_history_id   = Column(Integer, ForeignKey("analysis_history.id"), nullable=True, index=True)
    symbol                = Column(String(30), nullable=False, index=True)
    created_at            = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    horizon_days          = Column(Integer, nullable=False, default=30)

    # Prediction inputs
    recommendation        = Column(String(20), nullable=False)   # BULLISH / BEARISH / HOLD
    confidence_pct        = Column(Integer, nullable=False)       # final fused value (0–100)
    llm_confidence        = Column(Float, nullable=True)          # raw LLM output (0–100)
    quant_confidence      = Column(Float, nullable=True)          # QuantitativeEngine (0–1)
    ml_confidence         = Column(Float, nullable=True)          # ml-engine (0–1)
    venn_abers_confidence = Column(Float, nullable=True)          # Venn-Abers calibrated (0–1)
    signal_agreement      = Column(Float, nullable=True)          # bull/bear vote ratio (0–1)
    ml_engine_mode        = Column(String(50), nullable=True)     # "fallback_technical_heuristic" / "lgbm_trained"
    model_version         = Column(String(50), nullable=True, default="nivesh-v1.0-heuristic")
    scan_type             = Column(String(50), nullable=True, default="standard")
    regime_id             = Column(String(50), nullable=True)     # Market regime context

    # Prices at prediction time
    entry_price           = Column(Float, nullable=True)
    target_price          = Column(Float, nullable=True)          # medium 12m target

    # Outcome fields — filled by nightly outcome tracker
    actual_return_7d      = Column(Float, nullable=True)
    actual_return_30d     = Column(Float, nullable=True)
    actual_return_90d     = Column(Float, nullable=True)
    hit_direction_7d      = Column(Boolean, nullable=True)        # predicted direction matched 7d reality
    hit_direction_30d     = Column(Boolean, nullable=True)        # predicted direction matched 30d reality
    hit_direction_90d     = Column(Boolean, nullable=True)        # predicted direction matched 90d reality
    brier_score_7d        = Column(Float, nullable=True)          # (confidence - outcome)^2 for 7d
    brier_score_30d       = Column(Float, nullable=True)          # (confidence - outcome)^2 for 30d
    brier_score_90d       = Column(Float, nullable=True)          # (confidence - outcome)^2 for 90d

    __table_args__ = (
        Index("ix_ap_symbol_created", "symbol", "created_at"),
        Index("ix_ap_model_version", "model_version"),
    )

# ── Fundamentals Expansion Models ─────────────────────────────────

class CompanyFinancial(Base):
    """Stores company fundamental financial statement data."""
    __tablename__ = "company_financials"
    id = Column(Integer, primary_key=True, index=True)
    ticker = Column(String(30), nullable=False, index=True)
    period = Column(String(20), nullable=False) # e.g. "FY26" or "Q1_2026"
    revenue = Column(Float, nullable=True)
    net_income = Column(Float, nullable=True)
    eps = Column(Float, nullable=True)
    operating_margin = Column(Float, nullable=True)
    free_cash_flow = Column(Float, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

class ShareholdingPattern(Base):
    """Records quarter-by-quarter shareholding patterns for companies."""
    __tablename__ = "shareholding_patterns"
    id = Column(Integer, primary_key=True, index=True)
    ticker = Column(String(30), nullable=False, index=True)
    quarter = Column(String(20), nullable=False) # e.g. "Q1_2026"
    promoter_pct = Column(Float, nullable=True)
    fii_pct = Column(Float, nullable=True)
    dii_pct = Column(Float, nullable=True)
    public_pct = Column(Float, nullable=True)
    pledged_pct = Column(Float, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

class CorporateAction(Base):
    """Records corporate actions like dividends, splits, and bonuses."""
    __tablename__ = "corporate_actions"
    id = Column(Integer, primary_key=True, index=True)
    ticker = Column(String(30), nullable=False, index=True)
    ex_date = Column(String(20), nullable=False)
    record_date = Column(String(20), nullable=True)
    purpose = Column(String(200), nullable=False)
    dividend_amount = Column(Float, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

class CompanyValuation(Base):
    """Records point-in-time valuation metrics for companies."""
    __tablename__ = "company_valuations"
    id = Column(Integer, primary_key=True, index=True)
    ticker = Column(String(30), nullable=False, index=True)
    date = Column(String(20), nullable=False)
    current_pe = Column(Float, nullable=True)
    forward_pe = Column(Float, nullable=True)
    pb_ratio = Column(Float, nullable=True)
    ev_ebitda = Column(Float, nullable=True)
    market_cap = Column(Float, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

class RiskSignal(Base):
    """Records detected risk signals and red flags for companies."""
    __tablename__ = "risk_signals"
    id = Column(Integer, primary_key=True, index=True)
    ticker = Column(String(30), nullable=False, index=True)
    date = Column(String(20), nullable=False)
    signal_type = Column(String(50), nullable=False)
    severity = Column(String(20), nullable=False) # HIGH / MEDIUM / LOW
    description = Column(Text, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class YouTubeVideoSummary(Base):
    """Stores AI-generated summaries and transcript metadata for YouTube videos."""
    __tablename__ = "youtube_video_summaries"

    id                      = Column(Integer, primary_key=True, index=True)
    video_id                = Column(String(20), unique=True, index=True, nullable=False)
    url                     = Column(Text, nullable=False)
    title                   = Column(Text, default="")
    channel                 = Column(Text, default="")
    duration_seconds        = Column(Integer, default=0)
    transcript_hash         = Column(String(64), default="")
    transcript_source       = Column(String(50), default="")
    summary_provider        = Column(String(50), default="")
    summary_json            = Column(Text, default="{}")
    timestamps_json         = Column(Text, default="[]")
    raw_transcript_preview  = Column(Text, default="")
    estimated_input_tokens  = Column(Integer, default=0)
    estimated_output_tokens = Column(Integer, default=0)
    created_at              = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at              = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
    last_accessed_at        = Column(DateTime, nullable=True)


class UserPreference(Base):
    """User theme and notification preferences."""
    __tablename__ = "user_preferences"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, unique=True, index=True)
    theme = Column(String(50), default="banknote_standard")
    alerts_enabled = Column(Boolean, default=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    user = relationship("User", backref="preferences")


class UserSubscription(Base):
    """User premium subscription/tier record.

    MOCK — simulated for demo purposes. No real payment processor or
    StoreKit purchase completion is wired here; services/subscription_service.py's
    mock_upgrade()/mock_cancel() just flip these columns directly.

    Cancellation semantics: mock_cancel() sets is_active=False and
    cancelled_at=now but deliberately leaves `tier` unchanged until
    `renews_at` — i.e. the user logically keeps access through the end of
    the billing period they already paid for. Once `renews_at` passes for a
    cancelled (is_active=False) subscription, the tier should logically be
    treated as "free" again, but there is NO cron/scheduled job in this repo
    that flips `tier` back to "free" automatically — callers that care about
    "is this subscription still actually entitled" should check
    `is_active` and compare `renews_at` to now rather than trusting `tier`
    alone once `is_active` is False.
    """
    __tablename__ = "user_subscriptions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, unique=True, index=True)
    tier = Column(String(20), nullable=False, default="free", server_default="free")
    billing_cycle = Column(String(20), nullable=True)  # "monthly" | "annual" | NULL (free tier)
    started_at = Column(DateTime, nullable=True)
    renews_at = Column(DateTime, nullable=True)
    is_active = Column(Boolean, nullable=False, default=True, server_default="1")
    cancelled_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    user = relationship("User", backref="subscription")

    __table_args__ = (
        CheckConstraint("tier IN ('free','pro','super_pro')", name="ck_user_subscription_tier"),
        CheckConstraint(
            "billing_cycle IN ('monthly','annual') OR billing_cycle IS NULL",
            name="ck_user_subscription_billing_cycle",
        ),
    )


class InAppNotification(Base):
    """In-app notification inbox for AI alerts, earnings, system messages."""
    __tablename__ = "in_app_notifications"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    type = Column(String(50), nullable=False)
    title = Column(String(200), nullable=False)
    body = Column(Text, nullable=False)
    is_read = Column(Boolean, default=False)
    action_url = Column(String(500), nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    user = relationship("User", backref="notifications")

class Watchlist(Base):
    """Stores user's watchlist tickers."""
    __tablename__ = "watchlists"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    ticker = Column(String(30), nullable=False, index=True)
    added_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    user = relationship("User", backref="watchlist_items")


class MutualFund(Base):
    """Stores mutual fund scheme details (MF Router).

    Legacy fields (fund_name, amc, category) are kept for backward
    compatibility with earlier migration da1855cd2742_add_mf_and_ipo.py —
    do not drop without a data migration. New code should prefer
    scheme_name/amc_name/category, kept in sync with the legacy columns
    by the service layer.
    """
    __tablename__ = "mutual_funds"

    id = Column(Integer, primary_key=True, index=True)

    # Legacy fields (kept for backward compatibility)
    fund_name = Column(String(200), nullable=False, index=True)
    amc = Column(String(100), nullable=False)
    category = Column(String(50), nullable=False)

    # MF Router fields
    scheme_code = Column(String(30), unique=True, nullable=True, index=True)
    scheme_name = Column(String(200), nullable=True, index=True)
    amc_name = Column(String(100), nullable=True)
    sub_category = Column(String(50), nullable=True)
    nav = Column(Float, nullable=True)
    nav_date = Column(String(20), nullable=True)
    aum_cr = Column(Float, nullable=True)  # Assets Under Management, INR Crores
    expense_ratio = Column(Float, nullable=True)  # percent
    returns_1y = Column(Float, nullable=True)  # percent
    returns_3y = Column(Float, nullable=True)  # percent, annualized (CAGR)
    returns_5y = Column(Float, nullable=True)  # percent, annualized (CAGR)
    risk_level = Column(String(20), nullable=True)  # Low/Moderate/High/Very High
    fund_manager = Column(String(100), nullable=True)
    is_direct_plan = Column(Boolean, nullable=True, default=True)
    is_growth_plan = Column(Boolean, nullable=True, default=True)

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )


class IPOListing(Base):
    """Stores upcoming, open, and closed/listed IPO details (IPO Hub)."""
    __tablename__ = "ipo_listings"

    id = Column(Integer, primary_key=True, index=True)
    company_name = Column(String(200), nullable=False, index=True)
    symbol = Column(String(30), nullable=True, index=True)

    # Legacy fields (kept for backward compatibility with earlier migration
    # da1855cd2742_add_mf_and_ipo.py — do not drop without a data migration).
    issue_price_min = Column(Float, nullable=True)
    issue_price_max = Column(Float, nullable=True)
    subscription_status = Column(Text, nullable=True)

    # IPO Hub fields
    price_band_low = Column(Float, nullable=True)
    price_band_high = Column(Float, nullable=True)
    lot_size = Column(Integer, nullable=True)
    issue_size_cr = Column(Float, nullable=True)  # total issue size in INR Crores
    open_date = Column(String(20), nullable=True)
    close_date = Column(String(20), nullable=True)
    listing_date = Column(String(20), nullable=True)
    status = Column(String(20), nullable=True, index=True)  # upcoming|open|closed|listed
    subscription_qib = Column(Float, nullable=True)  # times subscribed (e.g. 2.5 = 2.5x)
    subscription_nii = Column(Float, nullable=True)
    subscription_retail = Column(Float, nullable=True)
    gmp = Column(Float, nullable=True)  # Grey Market Premium, INR per share

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )


# ---------------------------------------------------------------------------
# Community Forum (message boards, threads, replies, polls, votes)
# ---------------------------------------------------------------------------

class ForumBoard(Base):
    """A discussion board — either a general market board or a per-stock board."""
    __tablename__ = "forum_boards"

    id = Column(Integer, primary_key=True, index=True)
    slug = Column(String(60), unique=True, nullable=False, index=True)
    name = Column(String(150), nullable=False)
    description = Column(Text, nullable=True)
    board_type = Column(String(20), nullable=False, default="general")  # general|stock
    ticker = Column(String(30), nullable=True, index=True)  # set when board_type == "stock"

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    threads = relationship("ForumThread", back_populates="board", cascade="all, delete-orphan")


class ForumThread(Base):
    """A discussion thread belonging to a single board, opened by one user."""
    __tablename__ = "forum_threads"

    id = Column(Integer, primary_key=True, index=True)
    board_id = Column(Integer, ForeignKey("forum_boards.id"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    title = Column(String(200), nullable=False)
    is_pinned = Column(Boolean, nullable=False, default=False, server_default="0")

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    board = relationship("ForumBoard", back_populates="threads")
    posts = relationship("ForumPost", back_populates="thread", cascade="all, delete-orphan")
    poll = relationship("ForumPoll", back_populates="thread", uselist=False, cascade="all, delete-orphan")


class ForumPost(Base):
    """A post inside a thread. The first post (is_op=True) holds the thread body;
    subsequent posts are replies. parent_post_id supports nested replies.
    """
    __tablename__ = "forum_posts"

    id = Column(Integer, primary_key=True, index=True)
    thread_id = Column(Integer, ForeignKey("forum_threads.id"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    parent_post_id = Column(Integer, ForeignKey("forum_posts.id"), nullable=True, index=True)
    body = Column(Text, nullable=False)
    is_op = Column(Boolean, nullable=False, default=False, server_default="0")

    # Denormalized vote counters — source of truth for idempotent voting lives in ForumVote.
    upvotes = Column(Integer, nullable=False, default=0, server_default="0")
    downvotes = Column(Integer, nullable=False, default=0, server_default="0")

    # Moderation verdict from services/forum_moderation_service.py:moderate_post(),
    # applied at creation time in services/forum_service.py:create_post().
    moderation_action = Column(String(10), nullable=False, default="allow", server_default="allow")  # allow|flag|block
    spam_score = Column(Integer, nullable=True)
    sentiment = Column(String(10), nullable=True)  # bullish|bearish|neutral

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    thread = relationship("ForumThread", back_populates="posts")


class ForumPoll(Base):
    """A poll attached 1:1 to a thread."""
    __tablename__ = "forum_polls"

    id = Column(Integer, primary_key=True, index=True)
    thread_id = Column(Integer, ForeignKey("forum_threads.id"), unique=True, nullable=False, index=True)
    question = Column(String(300), nullable=False)

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    thread = relationship("ForumThread", back_populates="poll")
    options = relationship("ForumPollOption", back_populates="poll", cascade="all, delete-orphan")


class ForumPollOption(Base):
    """A single answer option belonging to a poll."""
    __tablename__ = "forum_poll_options"

    id = Column(Integer, primary_key=True, index=True)
    poll_id = Column(Integer, ForeignKey("forum_polls.id"), nullable=False, index=True)
    option_text = Column(String(150), nullable=False)
    vote_count = Column(Integer, nullable=False, default=0, server_default="0")

    poll = relationship("ForumPoll", back_populates="options")


class ForumVote(Base):
    """Tracks one vote per user per post (up/down) or per poll (single option pick).
    Idempotency/toggle logic lives in services/forum_service.py; the unique
    constraints here just guarantee "one vote per user per target" at the DB level.
    """
    __tablename__ = "forum_votes"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    post_id = Column(Integer, ForeignKey("forum_posts.id"), nullable=True, index=True)
    poll_id = Column(Integer, ForeignKey("forum_polls.id"), nullable=True, index=True)
    poll_option_id = Column(Integer, ForeignKey("forum_poll_options.id"), nullable=True, index=True)
    vote_value = Column(Integer, nullable=False, default=1)  # +1 up / -1 down for posts; +1 for poll picks

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        UniqueConstraint("user_id", "post_id", name="uq_forum_vote_user_post"),
        UniqueConstraint("user_id", "poll_id", name="uq_forum_vote_user_poll"),
    )


# ---------------------------------------------------------------------------
# KYC / consent-management — loan marketplace
#
# MOCK DATA / SIMULATED — these models back a demo "SIM-binding"-style device
# consent check and a granular consent ledger for the loan marketplace's KYC
# flow. Nothing here talks to a real telecom carrier or credit bureau; see
# services/kyc_consent_service.py for the simulated verification logic.
# ---------------------------------------------------------------------------

class KYCConsent(Base):
    """Audit-trail record of a single consent grant/revocation.

    Rows are never deleted — revoke_consent() sets revoked_at instead, so the
    full consent history remains inspectable for compliance/audit purposes.
    """
    __tablename__ = "kyc_consents"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    # e.g. "data_sharing" | "credit_check" | "sim_binding"
    consent_type = Column(String(40), nullable=False, index=True)
    granted = Column(Boolean, nullable=False, default=False, server_default="0")
    granted_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    ip_address = Column(String(64), nullable=True)
    revoked_at = Column(DateTime, nullable=True)


class DeviceBinding(Base):
    """MOCK DATA — simulated SIM-binding / device-consent record.

    NOT a real telecom SIM-swap-detection integration. Simply stores which
    device_id(s) a user has registered so verify_device_binding() can do a
    simulated match check for the KYC flow demo.
    """
    __tablename__ = "device_bindings"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    device_id = Column(String(120), nullable=False, index=True)
    bound_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    is_primary = Column(Boolean, nullable=False, default=True, server_default="1")

    __table_args__ = (
        UniqueConstraint("user_id", "device_id", name="uq_device_binding_user_device"),
    )


# ---------------------------------------------------------------------------
# Loan Marketplace — MOCK NBFC / credit-bureau demo feature.
# Owned by services/loan_marketplace_service.py + services/credit_bureau_mock_service.py,
# exposed via routers/finance.py. All data here is simulated for demo
# purposes — no real NBFC or credit-bureau integration.
# ---------------------------------------------------------------------------

class LinkedBankAccount(Base):
    """MOCK DATA — a simulated bank account a user has "linked" for the loan
    marketplace demo (e.g. for auto-debit / income-verification display).

    NOT a real account-aggregator / bank integration — no real account
    numbers or credentials are collected; values are user-supplied labels.
    """
    __tablename__ = "linked_bank_accounts"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    bank_name = Column(String(100), nullable=False)
    account_type = Column(String(20), nullable=False, default="savings", server_default="savings")  # savings|current
    masked_account_number = Column(String(20), nullable=False)  # e.g. "XXXX1234" — never a real account number
    ifsc_code = Column(String(15), nullable=True)
    is_primary = Column(Boolean, nullable=False, default=True, server_default="1")
    linked_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        UniqueConstraint("user_id", "masked_account_number", name="uq_linked_bank_account_user_number"),
    )


class LoanOffer(Base):
    """MOCK DATA — simulated NBFC loan product listed on the loan marketplace.

    Seeded by services/loan_marketplace_service.py:seed_mock_loan_offers_if_empty().
    Not a real NBFC product catalog / rate-card integration.
    """
    __tablename__ = "loan_offers"

    id = Column(Integer, primary_key=True, index=True)
    nbfc_name = Column(String(100), nullable=False)
    loan_type = Column(String(20), nullable=False, index=True)  # personal|home|car|gold|education
    min_amount = Column(Numeric(14, 2), nullable=False)
    max_amount = Column(Numeric(14, 2), nullable=False)
    interest_rate_pct = Column(Numeric(5, 2), nullable=False)  # annual, e.g. 10.50
    min_tenure_months = Column(Integer, nullable=False)
    max_tenure_months = Column(Integer, nullable=False)
    min_credit_score = Column(Integer, nullable=False, default=650, server_default="650")
    processing_fee_pct = Column(Numeric(5, 2), nullable=False, default=1.0, server_default="1.0")
    is_active = Column(Boolean, nullable=False, default=True, server_default="1")
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    applications = relationship("LoanApplication", back_populates="loan_offer", cascade="all, delete-orphan")


class LoanApplication(Base):
    """A user's application against a LoanOffer. status is driven by the
    demo underwriting rule in services/loan_marketplace_service.py — a
    simplified, clearly-mocked stand-in for real NBFC underwriting.
    """
    __tablename__ = "loan_applications"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    loan_offer_id = Column(Integer, ForeignKey("loan_offers.id"), nullable=False, index=True)
    requested_amount = Column(Numeric(14, 2), nullable=False)
    requested_tenure_months = Column(Integer, nullable=False)
    status = Column(String(20), nullable=False, default="submitted", server_default="submitted", index=True)
    # submitted|under_review|approved|rejected|disbursed
    mock_credit_score_at_application = Column(Integer, nullable=True)
    decision_reason = Column(Text, nullable=True)
    submitted_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    decided_at = Column(DateTime, nullable=True)

    loan_offer = relationship("LoanOffer", back_populates="applications")

    __table_args__ = (
        CheckConstraint(
            "status IN ('submitted','under_review','approved','rejected','disbursed')",
            name="ck_loan_application_status",
        ),
    )


# ---------------------------------------------------------------------------
# Compliance — India DPDP-Act-style right-to-erasure / consent-withdrawal
# demo. Owned by services/compliance_service.py, exposed via
# routers/compliance.py.
#
# DEMO-GRADE ONLY: DataDeletionRequest is a request/workflow state machine.
# Creating one (or moving it to "processing"/"completed") does NOT actually
# delete any user data anywhere in this codebase — see the explicit warning
# in compliance_service.request_account_deletion().
# ---------------------------------------------------------------------------

class AuditLogEntry(Base):
    """Append-only audit trail row for compliance-relevant actions
    (deletion requests, consent withdrawals, etc). Rows are never mutated
    or deleted once written.
    """
    __tablename__ = "audit_log_entries"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    action = Column(String(60), nullable=False, index=True)
    # Free-form JSON-serialisable details about the action (e.g. consent_type,
    # reason, previous/new status). Stored as JSON for structured audit reads.
    details = Column(JSON, nullable=True, default="{}")
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    ip_address = Column(String(64), nullable=True)


class DataDeletionRequest(Base):
    """Right-to-erasure workflow record (DPDP-Act style).

    DEMO ONLY — this table tracks REQUEST STATE for a data-deletion workflow.
    Reaching status "completed" here does not, by itself, delete any rows
    anywhere else in the database. See compliance_service.py.
    """
    __tablename__ = "data_deletion_requests"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    status = Column(String(20), nullable=False, default="pending", server_default="pending", index=True)
    # pending|processing|completed|cancelled
    requested_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    completed_at = Column(DateTime, nullable=True)
    reason = Column(Text, nullable=True)

    __table_args__ = (
        CheckConstraint(
            "status IN ('pending','processing','completed','cancelled')",
            name="ck_data_deletion_request_status",
        ),
    )
