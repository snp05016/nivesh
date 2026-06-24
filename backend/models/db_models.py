"""SQLAlchemy ORM model definitions for the Nivesh application."""

from datetime import datetime, timezone

from sqlalchemy import (
    Boolean, CheckConstraint, Column, DateTime, Float, Integer, JSON, String, Text,
    ForeignKey, Index, UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, relationship


class Base(DeclarativeBase):
    pass


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

class User(Base):
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
    created_at    = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    user = relationship("User", back_populates="portfolio")

    __table_args__ = (
        Index("ix_portfolio_user_id", "user_id"),
        Index("ix_portfolio_user_ticker", "user_id", "ticker"),
        Index("ix_portfolio_group", "user_id", "group_name"),
        UniqueConstraint("user_id", "ticker", "group_name", name="uq_portfolio_user_ticker_group"),
        CheckConstraint("group_name = 'watchlist' OR shares > 0", name="ck_portfolio_shares_positive"),
        CheckConstraint("group_name = 'watchlist' OR buy_price > 0", name="ck_portfolio_buy_price_positive"),
    )


class AnalysisHistory(Base):
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
    created_at     = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    user = relationship("User", back_populates="trade_journal")

    __table_args__ = (
        Index("ix_trade_journal_user_id", "user_id"),
    )


class DeviceToken(Base):
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
    except Exception:
        pass  # telemetry must never cause a cascading failure


class EarningsAlert(Base):
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
    except Exception:
        pass  # telemetry must never cascade


class BlockDeal(Base):
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
    except Exception:
        pass  # telemetry must never cascade


class AdvisorBiography(Base):
    __tablename__ = "advisor_biographies"

    id = Column(Integer, primary_key=True, index=True)
    advisor_name = Column(String(100), nullable=False, index=True)
    sebi_reg_number = Column(String(20), nullable=False, unique=True)
    experience_years = Column(Integer, default=0)
    analytical_framework = Column(String(200), nullable=True)  # e.g. "Wyckoff, Volume Profile"
    full_biography_text = Column(Text, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class TextAdvisoryInsight(Base):
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
    except Exception:
        pass  # telemetry must never cause a cascading failure


class MarketAnomaly(Base):
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
