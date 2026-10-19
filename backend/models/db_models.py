"""SQLAlchemy ORM model definitions for the Nivesh application."""

from datetime import datetime, timezone

from sqlalchemy import (
    Boolean, CheckConstraint, Column, Date, DateTime, Float, Integer, JSON, Numeric, String, Text,
    ForeignKey, Index, UniqueConstraint, text,
)
from sqlalchemy.orm import DeclarativeBase, deferred, relationship


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
    # AUTH-01: admin is this flag only (scripts/manage_users.py set-admin), never the username.
    is_admin      = Column(Boolean, nullable=False, default=False, server_default="0")
    # Bumped on password reset; JWT revocation check is AUTH-13.
    token_version = Column(Integer, nullable=False, default=0, server_default="0")
    # DB-06: set by compliance_service.erase_user(); the row stays as a tombstone
    # so retained audit/consent/forum rows keep a valid user_id.
    deleted_at    = Column(DateTime, nullable=True)

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
    group_name=watchlist uses shares=0/buy_price=0 as intentional sentinels; watchlist
    rows must set group_name="watchlist" explicitly (the default is "holdings").
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
    group_name    = Column(String(50), default="holdings")
    notes         = Column(Text, default="")
    is_virtual    = Column(Boolean, default=False, nullable=False, server_default="0")
    created_at    = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    group_id      = Column(Integer, ForeignKey("portfolio_groups.id"), nullable=True)
    # 'EQ' listed equity | 'MF' mutual fund (ticker is the ISIN); the latest ledger row's.
    asset_class   = Column(String(8), nullable=False, default="EQ", server_default="EQ")

    user = relationship("User", back_populates="portfolio")

    __table_args__ = (
        Index("ix_portfolio_user_id", "user_id"),
        Index("ix_portfolio_user_ticker", "user_id", "ticker"),
        Index("ix_portfolio_group", "user_id", "group_name"),
        Index("ix_portfolio_group_id", "group_id"),
        UniqueConstraint("user_id", "ticker", "group_name", name="uq_portfolio_user_ticker_group"),
        CheckConstraint("group_name = 'watchlist' OR shares > 0", name="ck_portfolio_shares_positive"),
        CheckConstraint("group_name = 'watchlist' OR buy_price > 0", name="ck_portfolio_buy_price_positive"),
        CheckConstraint("asset_class IN ('EQ','MF')", name="ck_portfolio_asset_class"),
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
        # DB-09: at most one default group per user.
        Index(
            "uq_portfolio_groups_one_default",
            "user_id",
            unique=True,
            sqlite_where=text("is_default = 1"),
            postgresql_where=text("is_default"),
        ),
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
    # DB-09: client Idempotency-Key; a retried POST returns the first row.
    client_request_id = Column(String(64), nullable=True)
    asset_class      = Column(String(8), nullable=False, default="EQ", server_default="EQ")
    # Rows written by a statement import (CAS); NULL for manual and internal rows.
    import_batch_id  = Column(
        Integer,
        ForeignKey("import_batches.id", name="fk_portfolio_transactions_import_batch", ondelete="SET NULL"),
        nullable=True,
    )

    __table_args__ = (
        Index("ix_portfolio_transactions_user_id", "user_id"),
        Index("ix_portfolio_transactions_import_batch", "import_batch_id"),
        Index("ix_portfolio_transactions_ticker", "ticker"),
        Index("ix_portfolio_transactions_group_id", "group_id"),
        Index("ix_portfolio_transactions_date", "date"),
        Index("uq_portfolio_transactions_client_req", "user_id", "client_request_id", unique=True),
        # ADJUST to 0 shares (close_position) needs >= 0.
        CheckConstraint("quantity >= 0", name="ck_portfolio_transactions_quantity_nonneg"),
        CheckConstraint("price >= 0", name="ck_portfolio_transactions_price_nonneg"),
        CheckConstraint(
            "transaction_type IN ('BUY','SELL','SPLIT','BONUS','DIVIDEND','ADJUST')",
            name="ck_portfolio_transactions_type",
        ),
        CheckConstraint("asset_class IN ('EQ','MF')", name="ck_portfolio_transactions_asset_class"),
    )


class ImportBatch(Base):
    """One statement upload (CAS): parsing -> previewed -> committed, or failed/cancelled.

    A file can be committed once per user (partial unique index); previews of the
    same file may repeat. Ledger rows it wrote carry import_batch_id.
    """
    __tablename__ = "import_batches"

    id                     = Column(Integer, primary_key=True, autoincrement=True)
    user_id                = Column(Integer, ForeignKey("users.id"), nullable=False)
    source                 = Column(String(16), nullable=False, default="cams_kfintech", server_default="cams_kfintech")
    status                 = Column(String(12), nullable=False)
    file_sha256            = Column(String(64), nullable=True)
    cas_type               = Column(String(10), nullable=True)
    statement_from         = Column(Date, nullable=True)
    statement_to           = Column(Date, nullable=True)
    preview_json           = Column(JSON, nullable=True)
    error_code             = Column(String(40), nullable=True)
    schemes_total          = Column(Integer, nullable=False, default=0, server_default="0")
    schemes_imported       = Column(Integer, nullable=False, default=0, server_default="0")
    inserted_rows          = Column(Integer, nullable=False, default=0, server_default="0")
    skipped_rows           = Column(Integer, nullable=False, default=0, server_default="0")
    consent_notice_version = Column(String(16), nullable=True)
    consented_at           = Column(DateTime, nullable=True)
    created_at             = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    committed_at           = Column(DateTime, nullable=True)

    __table_args__ = (
        Index("ix_import_batches_user_created", "user_id", "created_at"),
        Index(
            "uq_import_batches_user_file_committed",
            "user_id",
            "file_sha256",
            unique=True,
            postgresql_where=text("status = 'committed'"),
            sqlite_where=text("status = 'committed'"),
        ),
        CheckConstraint(
            "status IN ('parsing','previewed','committed','failed','cancelled')",
            name="ck_import_batches_status",
        ),
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
        CheckConstraint("quantity > 0", name="ck_multi_asset_tx_quantity_positive"),
        CheckConstraint("price >= 0", name="ck_multi_asset_tx_price_nonneg"),
        CheckConstraint("fees >= 0", name="ck_multi_asset_tx_fees_nonneg"),
        CheckConstraint(
            "asset_type IN ('STOCK','MF','GOLD','FD')",
            name="ck_multi_asset_tx_asset_type",
        ),
        CheckConstraint(
            "transaction_type IN ('BUY','SELL','DEPOSIT','WITHDRAWAL','MATURITY')",
            name="ck_multi_asset_tx_type",
        ),
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
    # Multi-agent transcript: deferred so entity queries skip it; read only where needed (PERF-08).
    raw_output     = deferred(Column(Text, nullable=True))
    full_json      = Column(Text, nullable=False)
    scan_type      = Column(String(20), nullable=False, default="standard")
    # Epistemic feedback loop — added 2026-06-03
    outcome_delta_pct    = Column(Float, nullable=True)   # % price change since analysis
    was_correct          = Column(Boolean, nullable=True)  # signal matched price direction
    outcome_checked_at   = Column(DateTime, nullable=True)
    # ML Hybrid Pipeline — quantitative engine columns (added 2026-06-14)
    market_regime               = Column(String, nullable=True)
    calibrated_confidence        = Column(Float, nullable=True, default=0.0, server_default="0.0")
    confidence_math_breakdown   = Column(JSON, default=dict)
    conformal_target_upper_3m   = Column(Float, nullable=True)
    conformal_target_lower_3m   = Column(Float, nullable=True)
    quantitative_drivers        = Column(JSON, default=dict)
    tail_risk_flags             = Column(JSON, default=dict)
    created_at     = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    user = relationship("User", back_populates="analysis_history")

    __table_args__ = (
        Index("ix_analysis_history_user_id", "user_id"),
        Index("ix_analysis_history_ticker", "ticker"),
        Index("ix_analysis_history_scan_type", "scan_type"),
        Index("ix_analysis_history_created_at", "created_at"),
        Index("ix_analysis_history_ticker_user", "ticker", "user_id"),
        # PERF-15: earnings date filters and the latest-scan cache gate.
        Index("ix_analysis_history_analysis_date", "analysis_date"),
        Index("ix_analysis_history_ticker_scan_created", "ticker", "scan_type", "created_at"),
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

    job_id       = Column(String(36), primary_key=True)                  # full uuid4
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
        Index("ix_analysis_jobs_status_created", "status", "created_at"),  # PERF-15: SSE/monitor scans
        # One active job per user and scan_type, enforced atomically (DB-11).
        Index(
            "uq_analysis_jobs_active_user_scan", "user_id", "scan_type",
            unique=True,
            sqlite_where=text("status IN ('QUEUED', 'RUNNING')"),
            postgresql_where=text("status IN ('QUEUED', 'RUNNING')"),
        ),
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
        Index("ix_price_targets_triggered_ticker", "triggered", "ticker"),  # PERF-15: alert poller
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
    # Final market comparison per horizon, written once: {"21": {...}, "63": {...}}.
    market_score   = Column(JSON, nullable=True)

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

    __table_args__ = (
        Index("ix_news_articles_published_at", "published_at"),  # PERF-15: home feed, sentiment trend
    )


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

    __table_args__ = (
        # PERF-15: home feed filters/sorts on these.
        Index("ix_youtube_videos_published_at", "published_at"),
        Index("ix_youtube_videos_ticker_views", "matched_ticker", "view_count"),
    )


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
    tickers_list = Column(JSON, default=list)
    data_matrix = Column(JSON, default=list)
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


class AnalysisPrediction(Base):
    """Stores machine learning and quantitative predictions for analysis jobs."""
    __tablename__ = "analysis_predictions"

    id                    = Column(Integer, primary_key=True, autoincrement=True)
    analysis_history_id   = Column(Integer, ForeignKey("analysis_history.id"), nullable=True, index=True, unique=True)
    symbol                = Column(String(30), nullable=False, index=True)
    created_at            = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    horizon_days          = Column(Integer, nullable=False, default=20)  # label horizon in trading days

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

    # Provenance (ML-16): what the ml-engine saw and said, and which weights fused it
    ml_direction          = Column(Integer, nullable=True)        # -1 / 0 / 1 from ml-engine
    ml_p_up               = Column(Float, nullable=True)          # ml-engine raw P(up)
    input_asof_date       = Column(Date, nullable=True)           # last OHLCV bar fed to the model
    weights_version       = Column(String(40), nullable=True)     # fusion weight set used
    ml_fallback_used      = Column(Boolean, nullable=True)        # ml-engine fell back to heuristic
    target_date           = Column(Date, nullable=True)           # input_asof_date + horizon_days business days

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
    # Label at the model's own horizon: input_asof_date -> target_date (ML-15)
    actual_return_target  = Column(Float, nullable=True)
    hit_direction_target  = Column(Boolean, nullable=True)
    brier_score_target    = Column(Float, nullable=True)
    # Outcome lifecycle (ML-15): pending / abstain / scored / unresolvable
    outcome_status        = Column(String(20), nullable=False, default="pending", server_default="pending")
    outcome_attempts      = Column(Integer, nullable=False, default=0, server_default="0")  # empty-history fetches
    benchmark_return_30d  = Column(Float, nullable=True)          # NIFTY 50 return over the same 30d window
    hit_vs_benchmark_30d  = Column(Boolean, nullable=True)        # direction matched the excess return

    __table_args__ = (
        Index("ix_ap_symbol_created", "symbol", "created_at"),
        Index("ix_ap_model_version", "model_version"),
        Index("ix_ap_outcome_status", "outcome_status"),
        # One prediction per symbol, input bar, scan type and model; legacy rows (no as-of date) are exempt.
        Index(
            "uq_ap_symbol_asof_scan_model",
            "symbol", "input_asof_date", "scan_type", "model_version",
            unique=True,
            postgresql_where=text("input_asof_date IS NOT NULL"),
            sqlite_where=text("input_asof_date IS NOT NULL"),
        ),
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
    # "hidden" is set by user reports (auto-hide threshold) or a moderator
    # resolving a ForumReport — hidden posts are filtered out of every read.
    moderation_action = Column(String(10), nullable=False, default="allow", server_default="allow")  # allow|flag|block|hidden
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


class ForumReport(Base):
    """A user's report against a forum post (App Store 1.2 UGC report flow).

    One report per reporter per post. The reporter stops seeing the post
    immediately; enough distinct open reports auto-hide it for everyone
    (services/forum_service.py:REPORT_AUTO_HIDE_THRESHOLD) and moderators
    resolve reports via /api/forum/admin/reports.
    """
    __tablename__ = "forum_reports"

    id = Column(Integer, primary_key=True, index=True)
    reporter_user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    post_id = Column(Integer, ForeignKey("forum_posts.id"), nullable=False, index=True)
    reason = Column(String(20), nullable=False)  # spam|abuse|misleading|pump_and_dump|other
    details = Column(Text, nullable=True)
    status = Column(String(12), nullable=False, default="open", server_default="open", index=True)
    # open|actioned|dismissed

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        UniqueConstraint("reporter_user_id", "post_id", name="uq_forum_report_reporter_post"),
    )


class UserBlock(Base):
    """One user blocking another — the blocker no longer sees the blocked
    user's forum threads or posts."""
    __tablename__ = "user_blocks"

    id = Column(Integer, primary_key=True, index=True)
    blocker_user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    blocked_user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        UniqueConstraint("blocker_user_id", "blocked_user_id", name="uq_user_block_pair"),
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
    # a key of disclosure_service.CONSENT_PURPOSES, e.g. "credit_check"
    consent_type = Column(String(40), nullable=False, index=True)
    granted = Column(Boolean, nullable=False, default=False, server_default="0")
    granted_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    ip_address = Column(String(64), nullable=True)
    revoked_at = Column(DateTime, nullable=True)
    # FINSEC-09: what the user agreed to (see disclosure_service).
    policy_version = Column(String(20), nullable=True)
    notice_hash = Column(String(64), nullable=True)  # sha256 hex of the notice
    purpose = Column(String(200), nullable=True)
    app_version = Column(String(20), nullable=True)

    __table_args__ = (
        # DB-10: at most one active (granted, not revoked) row per user + type.
        Index(
            "uq_kyc_consents_active",
            "user_id",
            "consent_type",
            unique=True,
            sqlite_where=text("granted = 1 AND revoked_at IS NULL"),
            postgresql_where=text("granted AND revoked_at IS NULL"),
        ),
    )


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


class DeviceBindingAttempt(Base):
    """MOCK DATA - simulated for demo purposes, not a real integration.

    Audit trail of every bind_device() call (successful or rejected), used
    by the mock SIM-binding fraud-signal heuristics in
    services/kyc_consent_service.py (cross-user device reuse detection and
    rebind rate limiting). Rows are never deleted/updated — this is an
    append-only audit log, not a real telecom fraud-detection feed.
    """
    __tablename__ = "device_binding_attempts"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    device_id = Column(String(120), nullable=False, index=True)
    attempted_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    # "bound" | "rejected_cross_user" | "rejected_rate_limit"
    outcome = Column(String(30), nullable=False)
    reason = Column(Text, nullable=True)


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
    # Client-supplied Idempotency-Key header: a retried POST returns this row.
    idempotency_key = Column(String(64), nullable=True)
    # FINSEC-26: Key Fact Statement for this amount/tenure, frozen at submit,
    # and when the applicant acknowledged it (NULL = not acknowledged).
    kfs_apr_pct = Column(Numeric(6, 2), nullable=True)
    kfs_total_fees = Column(Numeric(14, 2), nullable=True)
    kfs_acknowledged_at = Column(DateTime, nullable=True)

    loan_offer = relationship("LoanOffer", back_populates="applications")

    __table_args__ = (
        CheckConstraint(
            "status IN ('submitted','under_review','approved','rejected','disbursed')",
            name="ck_loan_application_status",
        ),
        UniqueConstraint("user_id", "idempotency_key", name="uq_loan_app_idem"),
    )


class LoanDisbursement(Base):
    """MOCK DATA — simulated for demo purposes, not a real integration. No
    real fund transfer, NBFC-to-bank settlement rail, or payment gateway is
    involved here — this models a lender "disbursing" an approved loan to
    the borrower's linked bank account as an instant mock settlement.

    Requires the borrower to already have a LinkedBankAccount (the loan
    marketplace one, defined above — NOT FinanceTrackerAccount) marked
    is_primary=True; if none exists, disbursement fails closed (no row is
    written) rather than silently no-op'ing — see
    services/loan_marketplace_service.py:disburse_loan(). Legacy "failed"
    rows may still exist. At most one "completed" row per application
    (partial unique index).
    """
    __tablename__ = "loan_disbursements"

    id = Column(Integer, primary_key=True, index=True)
    loan_application_id = Column(Integer, ForeignKey("loan_applications.id"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    linked_bank_account_id = Column(Integer, ForeignKey("linked_bank_accounts.id"), nullable=True, index=True)
    nbfc_name = Column(String(100), nullable=False)  # copied from the loan offer at disbursement time
    disbursed_amount = Column(Numeric(14, 2), nullable=False)
    status = Column(String(20), nullable=False, default="completed", server_default="completed", index=True)
    # pending|completed|failed — mock instant settlement defaults to "completed"
    disbursed_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    failure_reason = Column(Text, nullable=True)

    loan_application = relationship("LoanApplication")

    __table_args__ = (
        CheckConstraint(
            "status IN ('pending','completed','failed')",
            name="ck_loan_disbursement_status",
        ),
        Index(
            "uq_loan_disbursement_completed_per_app",
            "loan_application_id",
            unique=True,
            sqlite_where=text("status = 'completed'"),
            postgresql_where=text("status = 'completed'"),
        ),
    )


# ---------------------------------------------------------------------------
# Finance Tracker — MOCK personal-finance "linked account" demo. Owned by
# services/finance_tracker_service.py, exposed via routers/finance.py.
#
# NOTE: This is functionally distinct from LinkedBankAccount above, which
# backs the Loan Marketplace (no balance field, has ifsc_code/is_primary).
# FinanceTrackerAccount instead backs the standalone Finance Tracker tab —
# balances, sync timestamps, and a wallet/credit-card account type. Still
# entirely MOCK DATA — simulated for demo purposes, not a real
# account-aggregator / bank-linking (OAuth/Plaid-style) integration.
# ---------------------------------------------------------------------------

class FinanceTrackerAccount(Base):
    """MOCK DATA — a simulated "linked" bank/wallet account for the Finance
    Tracker tab (balance summary + spend-category breakdown).

    NOT a real account-aggregator / bank integration — no real account
    numbers or credentials are collected; masked_account_number and balance
    are fabricated server-side by finance_tracker_service.link_demo_account().
    """
    __tablename__ = "finance_tracker_accounts"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    bank_name = Column(String(100), nullable=False)
    account_type = Column(String(20), nullable=False, default="savings", server_default="savings")
    # savings|current|credit_card|wallet
    masked_account_number = Column(String(20), nullable=False)  # e.g. "XXXX1234" — never a real account number
    balance = Column(Numeric(14, 2), nullable=False, default=0, server_default="0")
    last_synced_at = Column(DateTime, nullable=True)
    is_mock = Column(Boolean, nullable=False, default=True, server_default="1")
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        CheckConstraint(
            "account_type IN ('savings','current','credit_card','wallet')",
            name="ck_finance_tracker_account_type",
        ),
    )


# ---------------------------------------------------------------------------
# Compliance — India DPDP-Act-style right-to-erasure / consent-withdrawal.
# Owned by services/compliance_service.py, exposed via routers/compliance.py
# and routers/account.py. A pending DataDeletionRequest is executed after a
# grace period by compliance_service.process_due_deletion_requests() (daily
# scheduler job), which runs erase_user() per ERASURE_POLICY.
# ---------------------------------------------------------------------------

class AuditLogEntry(Base):
    """Append-only audit trail row for compliance-relevant actions
    (deletion requests, consent withdrawals, etc). Rows are never deleted;
    erase_user() only clears ip_address and keeps them attributed to the
    tombstoned user.
    """
    __tablename__ = "audit_log_entries"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    action = Column(String(60), nullable=False, index=True)
    # Free-form JSON-serialisable details about the action (e.g. consent_type,
    # reason, previous/new status). Stored as JSON for structured audit reads.
    details = Column(JSON, nullable=True, default=dict)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    ip_address = Column(String(64), nullable=True)


class DataDeletionRequest(Base):
    """Right-to-erasure workflow record (DPDP-Act style).

    "completed" is set by compliance_service.erase_user() in the same
    transaction that erases the user's data.
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
        # At most one active (pending/processing) request per user.
        Index(
            "uq_data_deletion_active",
            "user_id",
            unique=True,
            sqlite_where=text("status IN ('pending','processing')"),
            postgresql_where=text("status IN ('pending','processing')"),
        ),
    )


# ---------------------------------------------------------------------------
# Fixed Deposits — MOCK NBFC/bank FD marketplace demo. Owned by
# services/fixed_deposit_service.py, exposed via routers/fixed_deposits.py.
#
# MOCK DATA — simulated for demo purposes, not a real integration. No real
# NBFC/bank FD issuer API is called anywhere behind this feature, and no
# real UPI/net-banking payment gateway processes any money. Bookings settle
# instantly in-process to simulate a completed transaction for demo
# purposes only.
# ---------------------------------------------------------------------------

class FixedDepositScheme(Base):
    """MOCK DATA — simulated bank/NBFC fixed-deposit product listed on the
    FD marketplace for discovery/comparison.

    Seeded by services/fixed_deposit_service.py:seed_mock_fd_schemes_if_empty().
    Not a real bank/NBFC FD rate-card integration.
    """
    __tablename__ = "fixed_deposit_schemes"

    id = Column(Integer, primary_key=True, index=True)
    issuer_name = Column(String(100), nullable=False)  # mock bank/NBFC name
    min_tenure_months = Column(Integer, nullable=False)
    max_tenure_months = Column(Integer, nullable=False)
    min_amount = Column(Numeric(14, 2), nullable=False)
    max_amount = Column(Numeric(14, 2), nullable=False)
    interest_rate_pct = Column(Numeric(5, 2), nullable=False)  # general annual rate, e.g. 7.25
    # additional rate applied for senior citizens (60+); demo does not
    # itself verify age — a purely illustrative comparison field.
    senior_citizen_bonus_pct = Column(Numeric(5, 2), nullable=False, default=0.50, server_default="0.50")
    is_active = Column(Boolean, nullable=False, default=True, server_default="1")
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    bookings = relationship("FixedDepositBooking", back_populates="scheme", cascade="all, delete-orphan")


class FixedDepositBooking(Base):
    """A user's MOCK fixed-deposit booking against a FixedDepositScheme.

    MOCK DATA — simulated instant settlement. status defaults to
    "confirmed" only after the MOCK KYC gate (active "sim_binding" consent +
    verified device binding, see services/fixed_deposit_service.py) passes;
    otherwise the booking is recorded as "failed" with a decision_reason.
    No real UPI/net-banking payment gateway is called.
    """
    __tablename__ = "fixed_deposit_bookings"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    scheme_id = Column(Integer, ForeignKey("fixed_deposit_schemes.id"), nullable=False, index=True)
    principal_amount = Column(Numeric(14, 2), nullable=False)
    tenure_months = Column(Integer, nullable=False)
    interest_rate_pct = Column(Numeric(5, 2), nullable=False)  # rate locked at booking time
    maturity_amount = Column(Numeric(14, 2), nullable=False)  # computed at booking time
    payment_method = Column(String(20), nullable=False)  # upi|net_banking
    status = Column(String(20), nullable=False, default="confirmed", server_default="confirmed", index=True)
    # pending|confirmed|failed
    decision_reason = Column(Text, nullable=True)
    booked_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    matures_at = Column(DateTime, nullable=True)
    # Client-supplied Idempotency-Key header: a retried POST returns this row.
    idempotency_key = Column(String(64), nullable=True)

    scheme = relationship("FixedDepositScheme", back_populates="bookings")

    __table_args__ = (
        CheckConstraint(
            "status IN ('pending','confirmed','failed')",
            name="ck_fixed_deposit_booking_status",
        ),
        CheckConstraint(
            "payment_method IN ('upi','net_banking')",
            name="ck_fixed_deposit_booking_payment_method",
        ),
        UniqueConstraint("user_id", "idempotency_key", name="uq_fd_booking_idem"),
    )


# ---------------------------------------------------------------------------
# Research Engine ledger (spec §8.1). Migration t4u5v6w7x8y9.
#
# research_runs         one row per nightly kick / outcome scoring / live-metrics run
# research_reports      stored ResearchReport JSON (nightly or on-demand) + prose
# research_predictions  the prediction ledger; prediction columns are never
#                       updated; outcome columns are written once by the scorer
#                       (repositories/research_repo.write_outcome_once)
# research_live_metrics weekly live track-record rows per (procedure, horizon)
#
# Imports are local to this section so the shared import block above stays
# untouched (several tracks edit it).
# ---------------------------------------------------------------------------

from datetime import date  # noqa: E402
from decimal import Decimal  # noqa: E402
from typing import Any, Optional  # noqa: E402

from sqlalchemy import Date, SmallInteger  # noqa: E402
from sqlalchemy.orm import Mapped, mapped_column  # noqa: E402


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class ResearchRun(Base):
    """One research job execution (nightly kick, outcome scoring or live metrics)."""
    __tablename__ = "research_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_uid: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)  # ml-engine run_id
    kind: Mapped[str] = mapped_column(String(16), nullable=False)
    market_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    stage: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)
    counts_json: Mapped[Optional[Any]] = mapped_column(JSON(none_as_null=True), nullable=True)
    error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # stale_run, engine_restarted, engine_busy, ...
    started_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_utcnow)
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    __table_args__ = (
        UniqueConstraint("run_uid", name="uq_research_runs_run_uid"),
        CheckConstraint("kind IN ('nightly','outcomes','live_metrics')", name="ck_research_runs_kind"),
        CheckConstraint(
            "status IN ('running','ok','degraded','failed','skipped_holiday')",
            name="ck_research_runs_status",
        ),
        Index("ix_research_runs_kind_market_date", "kind", "market_date"),
    )


class ResearchReportRow(Base):
    """A stored ResearchReport (contract research.v1) plus its validated prose."""
    __tablename__ = "research_reports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    report_uid: Mapped[str] = mapped_column(String(36), nullable=False)  # contract report_id (uuid4)
    symbol: Mapped[str] = mapped_column(String(30), nullable=False)
    isin: Mapped[Optional[str]] = mapped_column(String(12), nullable=True)
    as_of_date: Mapped[date] = mapped_column(Date, nullable=False)
    engine_version: Mapped[str] = mapped_column(String(40), nullable=False)
    procedure_id: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)
    run_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("research_runs.id"), nullable=True)
    origin: Mapped[str] = mapped_column(String(10), nullable=False)
    status: Mapped[str] = mapped_column(String(10), nullable=False)
    in_universe: Mapped[bool] = mapped_column(Boolean, nullable=False)
    requested_by_user_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)  # on-demand quota only
    report_json: Mapped[Any] = mapped_column(JSON, nullable=False)
    facts_hash: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    narrative_json: Mapped[Optional[Any]] = mapped_column(JSON(none_as_null=True), nullable=True)
    narrative_status: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)
    narrative_attempts: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0, server_default="0")
    narrative_failures_json: Mapped[Optional[Any]] = mapped_column(JSON(none_as_null=True), nullable=True)
    narrative_generated_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_utcnow)

    __table_args__ = (
        UniqueConstraint("report_uid", name="uq_research_reports_report_uid"),
        UniqueConstraint(
            "symbol", "as_of_date", "engine_version", "origin",
            name="uq_research_reports_symbol_date_engine_origin",
        ),
        CheckConstraint("origin IN ('nightly','on_demand')", name="ck_research_reports_origin"),
        CheckConstraint("status IN ('ok','degraded')", name="ck_research_reports_status"),
        CheckConstraint(
            "narrative_status IN ('llm_validated','template')",
            name="ck_research_reports_narrative_status",
        ),
        Index("ix_research_reports_symbol_as_of_date", "symbol", "as_of_date"),
    )


class ResearchPrediction(Base):
    """Prediction ledger row. Prediction columns are immutable; the outcome
    columns are written once (outcome_status 'pending' -> 'matured'|'void').
    report_id becomes NULL when the report is pruned (ON DELETE SET NULL)."""
    __tablename__ = "research_predictions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    report_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("research_reports.id", ondelete="SET NULL"), nullable=True,
    )
    symbol: Mapped[str] = mapped_column(String(30), nullable=False)
    isin: Mapped[Optional[str]] = mapped_column(String(12), nullable=True)
    as_of_date: Mapped[date] = mapped_column(Date, nullable=False)
    horizon_days: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    procedure_id: Mapped[str] = mapped_column(String(40), nullable=False)
    model_id: Mapped[str] = mapped_column(String(80), nullable=False)
    manifest_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    universe_id: Mapped[str] = mapped_column(String(20), nullable=False)
    evidence_tier: Mapped[str] = mapped_column(String(24), nullable=False)
    reason_codes: Mapped[Optional[Any]] = mapped_column(JSON(none_as_null=True), nullable=True)
    score: Mapped[float] = mapped_column(Float, nullable=False)
    rank_pct: Mapped[float] = mapped_column(Float, nullable=False)
    bucket: Mapped[Optional[int]] = mapped_column(SmallInteger, nullable=True)
    p_top_half: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    entry_close: Mapped[Decimal] = mapped_column(Numeric(14, 4), nullable=False)  # raw close, same snapshot
    feature_hash: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    expected_maturity_date: Mapped[date] = mapped_column(Date, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_utcnow)
    # Written once by the scorer:
    outcome_status: Mapped[str] = mapped_column(
        String(10), nullable=False, default="pending", server_default="pending",
    )
    void_reason: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)
    realized_return_pct: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    realized_excess_pp: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    realized_top_half: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    nifty50_return_pct: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    stale_exit: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    scored_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    scorer_version: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)

    __table_args__ = (
        UniqueConstraint("report_id", "horizon_days", name="uq_research_predictions_report_horizon"),
        UniqueConstraint(
            "symbol", "as_of_date", "horizon_days", "model_id",
            name="uq_research_predictions_symbol_date_horizon_model",
        ),
        CheckConstraint("horizon_days IN (21,63)", name="ck_research_predictions_horizon"),
        CheckConstraint(
            "outcome_status IN ('pending','matured','void')",
            name="ck_research_predictions_outcome_status",
        ),
        Index("ix_research_predictions_outcome_maturity", "outcome_status", "expected_maturity_date"),
        Index("ix_research_predictions_procedure_horizon_as_of", "procedure_id", "horizon_days", "as_of_date"),
    )


class ResearchLiveMetric(Base):
    """Weekly live track-record snapshot for one (procedure, horizon)."""
    __tablename__ = "research_live_metrics"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    procedure_id: Mapped[str] = mapped_column(String(40), nullable=False)
    horizon_days: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    computed_on: Mapped[date] = mapped_column(Date, nullable=False)
    live_status: Mapped[str] = mapped_column(String(16), nullable=False)
    live_gate_passed: Mapped[bool] = mapped_column(Boolean, nullable=False)
    matured_n: Mapped[int] = mapped_column(Integer, nullable=False)
    matured_dates: Mapped[int] = mapped_column(Integer, nullable=False)
    metrics_json: Mapped[Any] = mapped_column(JSON, nullable=False)  # full LiveMetricsResponse
    alarms_json: Mapped[Any] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_utcnow)

    __table_args__ = (
        UniqueConstraint(
            "procedure_id", "horizon_days", "computed_on",
            name="uq_research_live_metrics_procedure_horizon_day",
        ),
        CheckConstraint(
            "live_status IN ('collecting','ok','under_review')",
            name="ck_research_live_metrics_live_status",
        ),
    )


class LlmUsage(Base):
    """One paid LLM call: the ledger behind the per-user and global daily AI budgets
    (services/llm_budget.py). user_id has no FK so rows outlive deleted users; NULL means
    a system job or an anonymous route."""
    __tablename__ = "llm_usage"

    id                 = Column(Integer, primary_key=True, autoincrement=True)
    created_at         = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc), index=True)
    user_id            = Column(Integer, nullable=True)
    feature            = Column(String(64), nullable=False)
    model              = Column(String(80), nullable=False)
    input_tokens       = Column(Integer, nullable=False, default=0)
    output_tokens      = Column(Integer, nullable=False, default=0)
    cache_read_tokens  = Column(Integer, nullable=False, default=0)
    cache_write_tokens = Column(Integer, nullable=False, default=0)
    cost_usd           = Column(Float, nullable=False, default=0.0)

    __table_args__ = (
        Index("ix_llm_usage_user_created", "user_id", "created_at"),
    )


class SchedulerJobStatus(Base):
    """Last run of each scheduled job (SILENT-13). Written by the scheduler worker via
    core.dashboard_state._dash_update_harvest so every worker's dashboard can read it."""
    __tablename__ = "scheduler_job_status"

    job_name: Mapped[str] = mapped_column(String(64), primary_key=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    last_started_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    last_finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    last_error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    last_result_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_utcnow)
