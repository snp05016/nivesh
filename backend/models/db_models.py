"""SQLAlchemy ORM model definitions for the Nivesh application."""

from datetime import datetime, timezone

from sqlalchemy import (
    Boolean, Column, DateTime, Float, Integer, JSON, String, Text,
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
    created_at    = Column(DateTime, default=datetime.utcnow)

    portfolio        = relationship("Portfolio",       back_populates="user", cascade="all, delete-orphan")
    analysis_history = relationship("AnalysisHistory", back_populates="user", cascade="all, delete-orphan")
    price_targets    = relationship("PriceTarget",     back_populates="user", cascade="all, delete-orphan")
    trade_journal    = relationship("TradeJournal",    back_populates="user", cascade="all, delete-orphan")
    device_tokens    = relationship("DeviceToken",     back_populates="user", cascade="all, delete-orphan")


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
    buy_price    = Column(Float, nullable=False)
    group_name   = Column(String(50), default="watchlist")
    notes        = Column(Text, default="")
    created_at   = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="portfolio")

    __table_args__ = (
        Index("ix_portfolio_user_id", "user_id"),
        Index("ix_portfolio_user_ticker", "user_id", "ticker"),
        Index("ix_portfolio_group", "user_id", "group_name"),
    )


class AnalysisHistory(Base):
    __tablename__ = "analysis_history"

    id             = Column(Integer, primary_key=True, autoincrement=True)
    user_id        = Column(Integer, ForeignKey("users.id"), nullable=True)
    ticker         = Column(String(30), nullable=False)
    analysis_date  = Column(String(20), nullable=False)
    signal         = Column(String(20), nullable=False)
    confidence_pct = Column(Float, nullable=True)
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
    market_regime               = Column(String, default="Transition")
    calibrated_confidence       = Column(Float, default=0.0)
    confidence_math_breakdown   = Column(JSON, default=dict)
    conformal_target_upper_3m   = Column(Float, nullable=True)
    conformal_target_lower_3m   = Column(Float, nullable=True)
    quantitative_drivers        = Column(JSON, default=dict)
    tail_risk_flags             = Column(JSON, default=dict)
    created_at     = Column(DateTime, default=datetime.utcnow)

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
    created_at  = Column(DateTime, default=datetime.utcnow)


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
    created_at   = Column(DateTime, default=datetime.utcnow)
    started_at   = Column(DateTime, nullable=True)
    finished_at  = Column(DateTime, nullable=True)


class PriceTarget(Base):
    __tablename__ = "price_targets"

    id           = Column(Integer, primary_key=True, autoincrement=True)
    user_id      = Column(Integer, ForeignKey("users.id"), nullable=False)
    ticker       = Column(String(30), nullable=False)
    target_price = Column(Float, nullable=False)
    direction    = Column(String(10), nullable=False)
    triggered    = Column(Boolean, default=False)
    created_at   = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="price_targets")


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
    created_at     = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="trade_journal")


class DeviceToken(Base):
    __tablename__ = "device_tokens"

    id           = Column(Integer, primary_key=True, autoincrement=True)
    user_id      = Column(Integer, ForeignKey("users.id"), nullable=False)
    device_token = Column(String(200), unique=True, nullable=False)
    platform     = Column(String(10), default="ios")
    created_at   = Column(DateTime, default=datetime.utcnow)
    updated_at   = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="device_tokens")


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
    created_at      = Column(DateTime, default=datetime.utcnow)

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
    created_at      = Column(DateTime, default=datetime.utcnow)


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
    created_at      = Column(DateTime, default=datetime.utcnow)
    harvested_at    = Column(DateTime, default=datetime.utcnow)
    matched_ticker  = Column(String, nullable=True, index=True)
    source          = Column(String, default="channel_harvest")
    sebi_reg        = Column(String, nullable=True)


class PortfolioValuationHistory(Base):
    __tablename__ = "portfolio_valuation_history"

    id              = Column(Integer, primary_key=True, index=True)
    user_id         = Column(Integer, nullable=False, index=True)
    snapshot_date   = Column(String, nullable=False)        # "2026-06-02" ISO date string
    total_value     = Column(Float, nullable=False)         # Total portfolio value in INR
    total_invested  = Column(Float, nullable=False)         # Total cost basis
    total_pnl       = Column(Float, nullable=False)         # total_value - total_invested
    pnl_percent     = Column(Float, nullable=False)         # (pnl / invested) * 100
    nifty_close     = Column(Float, nullable=True)          # NIFTY 50 close that day (for benchmark)
    created_at      = Column(DateTime, default=datetime.utcnow)

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
    created_at      = Column(DateTime, default=datetime.utcnow)

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
    created_at      = Column(DateTime, default=datetime.utcnow)
    updated_at      = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

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
    created_at           = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", foreign_keys=[user_id])

    __table_args__ = (
        UniqueConstraint("user_id", "snapshot_date", name="uq_networth_user_date"),
    )


class MarketErrorLog(Base):
    __tablename__ = "market_error_logs"

    id             = Column(Integer, primary_key=True, index=True)
    timestamp      = Column(DateTime, default=datetime.utcnow)
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
    created_at    = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", foreign_keys=[user_id])

    __table_args__ = (
        UniqueConstraint("user_id", "ticker", "earnings_date", name="uq_user_ticker_earnings_date"),
    )


class EarningsErrorLog(Base):
    __tablename__ = "earnings_error_logs"

    id             = Column(Integer, primary_key=True, index=True)
    timestamp      = Column(DateTime, default=datetime.utcnow)
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
    created_at = Column(DateTime, default=datetime.utcnow)


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
    created_at = Column(DateTime, default=datetime.utcnow)


class NotificationErrorLog(Base):
    __tablename__ = "notification_error_logs"

    id            = Column(Integer, primary_key=True, index=True)
    timestamp     = Column(DateTime, default=datetime.utcnow)
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
    created_at = Column(DateTime, default=datetime.utcnow)


class TextAdvisoryInsight(Base):
    __tablename__ = "text_advisory_insights"

    id = Column(Integer, primary_key=True, index=True)
    advisor_id = Column(Integer, ForeignKey("advisor_biographies.id"), nullable=False, index=True)
    timestamp = Column(DateTime, default=datetime.utcnow)
    content_text = Column(Text, nullable=False)
    target_ticker = Column(String(30), nullable=True, index=True)
    extracted_sentiment = Column(String(20), nullable=True)  # BULLISH/BEARISH/NEUTRAL
    source_url = Column(String(500), nullable=True)

    advisor = relationship("AdvisorBiography", foreign_keys=[advisor_id])


class IdeasErrorLog(Base):
    __tablename__ = "ideas_error_logs"

    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, default=datetime.utcnow)
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
