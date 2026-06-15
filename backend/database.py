"""SQLite / PostgreSQL database setup, models, and seed data."""

from __future__ import annotations

import hashlib
import json
import os
import secrets
import uuid
import bcrypt
from datetime import datetime, date, timedelta, timezone

# Task 50: timezone-aware UTC helper replacing deprecated datetime.utcnow()
def _utcnow() -> datetime:
    return datetime.now(timezone.utc)
from pathlib import Path
from typing import Optional
from contextlib import contextmanager

from sqlalchemy import (
    Boolean, Column, DateTime, Float, Integer, JSON, String, Text,
    ForeignKey, Index, UniqueConstraint, create_engine, event, text,
)
from sqlalchemy.orm import DeclarativeBase, Session, relationship, sessionmaker

# ---------------------------------------------------------------------------
# Environment-aware engine — SQLite locally, PostgreSQL on DigitalOcean
# ---------------------------------------------------------------------------

_DEFAULT_SQLITE = f"sqlite:///{Path(__file__).parent / 'stockapp.db'}"
DATABASE_URL = os.getenv("DATABASE_URL", _DEFAULT_SQLITE)

if DATABASE_URL.startswith("postgresql"):
    # Task 48: improved connection pool settings
    ENGINE = create_engine(
        DATABASE_URL,
        pool_size=10,
        max_overflow=20,
        pool_pre_ping=True,
        pool_recycle=3600,
        echo=False,
    )
else:
    # SQLite — keep check_same_thread=False so FastAPI threads can share it
    ENGINE = create_engine(
        DATABASE_URL,
        connect_args={"check_same_thread": False},
        echo=False,
    )

    # Enable WAL mode for SQLite — better concurrent read performance
    @event.listens_for(ENGINE, "connect")
    def _set_sqlite_wal(dbapi_conn, _):
        dbapi_conn.execute("PRAGMA journal_mode=WAL")
        dbapi_conn.execute("PRAGMA synchronous=NORMAL")
        dbapi_conn.execute("PRAGMA busy_timeout=5000")

SessionLocal = sessionmaker(bind=ENGINE, autoflush=False, autocommit=False)


class Base(DeclarativeBase):
    pass


# Fix 2.47: reserved Python keywords that should never be used as raw ticker
# identifiers in SQL queries. SQLAlchemy parameterization handles these safely
# in filter_by(), but raw text() queries must be guarded.
_PYTHON_RESERVED_TICKERS = {
    "TRUE", "FALSE", "NONE", "AND", "OR", "NOT", "IF", "ELSE",
    "FOR", "WHILE", "CLASS", "DEF", "RETURN", "YIELD", "IMPORT",
    "FROM", "AS", "TRY", "EXCEPT", "FINALLY", "RAISE", "WITH",
    "IS", "IN", "LAMBDA", "GLOBAL", "NONLOCAL", "PASS", "BREAK",
    "CONTINUE", "DEL", "ASSERT", "ASYNC", "AWAIT",
}


def _validate_ticker_safe(ticker: str) -> str:
    """Ensure ticker string is safe for database operations.
    Returns cleaned ticker. Raises ValueError for empty/invalid input.
    SQLAlchemy ORM parameterization handles keyword tickers safely —
    this is a defense-in-depth check for raw SQL usage.
    """
    ticker = ticker.strip().upper()
    if not ticker:
        raise ValueError("Ticker cannot be empty")
    if len(ticker) > 30:
        raise ValueError(f"Ticker too long: {ticker}")
    if ticker.split(".")[0] in _PYTHON_RESERVED_TICKERS:
        import logging
        logging.getLogger("nivesh.database").warning(
            f"Ticker '{ticker}' matches Python reserved keyword. "
            "Ensure all queries use SQLAlchemy parameterization."
        )
    return ticker


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


# ─────────────────────────────────────────────────────────────────────────────
# TABLE: news_articles
# Populated by nightly news_harvester.py. Never written during request handling.
# ─────────────────────────────────────────────────────────────────────────────
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


# ─────────────────────────────────────────────────────────────────────────────
# TABLE: youtube_videos
# Populated by nightly youtube_harvester.py.
# ─────────────────────────────────────────────────────────────────────────────
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


# ─────────────────────────────────────────────────────────────────────────────
# TABLE: portfolio_valuation_history
# Populated by nightly portfolio_snapshot.py.
# ─────────────────────────────────────────────────────────────────────────────
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


# ─────────────────────────────────────────────────────────────────────────────
# TABLE: pkscreener_signals
# Populated by nightly pkscreener_runner.py.
# ─────────────────────────────────────────────────────────────────────────────
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


# ─────────────────────────────────────────────────────────────────────────────
# TABLE: macro_events
# Stores calendar events: RBI policy, earnings, economic releases, etc.
# ─────────────────────────────────────────────────────────────────────────────
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


# ─────────────────────────────────────────────────────────────────────────────
# TABLE: net_worth_ledger
# Tracks daily family net-worth snapshots per user.
# ─────────────────────────────────────────────────────────────────────────────
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


# ─────────────────────────────────────────────────────────────────────────────
# TABLE: market_error_logs
# Diagnostic telemetry — populated whenever a market data fetcher fails.
# Read by GET /api/v1/admin/error-logs for iOS console debugging.
# ─────────────────────────────────────────────────────────────────────────────
class MarketErrorLog(Base):
    __tablename__ = "market_error_logs"

    id             = Column(Integer, primary_key=True, index=True)
    timestamp      = Column(DateTime, default=datetime.utcnow)
    component      = Column(String(100), nullable=False)   # "filings_extractor", "nse_data_provider", etc.
    error_message  = Column(Text, nullable=False)            # full traceback / error string
    context_ticker = Column(String(30), nullable=True)       # optional — ticker being processed when error hit


def log_market_error(component: str, error_message: str, context_ticker: str | None = None) -> None:
    """Write a diagnostic error row to market_error_logs. Non-fatal — swallows its own errors."""
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


# ─────────────────────────────────────────────────────────────────────────────
# TABLE: earnings_alerts
# User-requested earnings date reminders. Written via POST, read via GET.
# ─────────────────────────────────────────────────────────────────────────────
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


# ─────────────────────────────────────────────────────────────────────────────
# TABLE: earnings_error_logs
# Telemetry for earnings-specific failures (calendar aggregation, feed scraping).
# Read by GET /api/v1/admin/earnings-errors for backend dashboard debugging.
# ─────────────────────────────────────────────────────────────────────────────
class EarningsErrorLog(Base):
    __tablename__ = "earnings_error_logs"

    id             = Column(Integer, primary_key=True, index=True)
    timestamp      = Column(DateTime, default=datetime.utcnow)
    module         = Column(String(100), nullable=False)   # "filings_extractor", "earnings_calendar", "earnings_feed"
    error_trace    = Column(Text, nullable=False)            # full traceback / error string
    failed_ticker  = Column(String(30), nullable=True)       # ticker being processed when error occurred


def log_earnings_error(module: str, error_trace: str, failed_ticker: str | None = None) -> None:
    """Write a diagnostic error row to earnings_error_logs. Non-fatal."""
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

# ─────────────────────────────────────────────────────────────────────────────
# TABLE: notification_error_logs
# Telemetry for push notification pipeline failures.
# Read by GET /api/v1/admin/notification-errors for backend dashboard debugging.
# ─────────────────────────────────────────────────────────────────────────────
class NotificationErrorLog(Base):
    __tablename__ = "notification_error_logs"

    id            = Column(Integer, primary_key=True, index=True)
    timestamp     = Column(DateTime, default=datetime.utcnow)
    failure_point = Column(String(100), nullable=False)   # "token_registration", "apns_dispatch"
    error_trace   = Column(Text, nullable=False)            # full traceback / error string
    target_device = Column(String(200), nullable=True)      # device token or identifier


def log_notification_error(failure_point: str, error_trace: str, target_device: str | None = None) -> None:
    """Write a diagnostic error row to notification_error_logs. Non-fatal."""
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


# ─────────────────────────────────────────────────────────────────────────────
# TABLE: advisor_biographies
# Verified SEBI-registered research analysts providing public market commentary.
# ─────────────────────────────────────────────────────────────────────────────
class AdvisorBiography(Base):
    __tablename__ = "advisor_biographies"

    id = Column(Integer, primary_key=True, index=True)
    advisor_name = Column(String(100), nullable=False, index=True)
    sebi_reg_number = Column(String(20), nullable=False, unique=True)
    experience_years = Column(Integer, default=0)
    analytical_framework = Column(String(200), nullable=True)  # e.g. "Wyckoff, Volume Profile"
    full_biography_text = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)


# ─────────────────────────────────────────────────────────────────────────────
# TABLE: text_advisory_insights
# Stores parsed text-based advisory content (newsletter excerpts, Twitter/X
# threads, blog posts). Populated by nightly ideas_harvester.py.
# ─────────────────────────────────────────────────────────────────────────────
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


# ─────────────────────────────────────────────────────────────────────────────
# TABLE: ideas_error_logs
# Diagnostic telemetry for Ideas workspace failures (advisor harvester, feed
# parser, etc.). Read by GET /api/v1/admin/ideas-errors.
# ─────────────────────────────────────────────────────────────────────────────
class IdeasErrorLog(Base):
    __tablename__ = "ideas_error_logs"

    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, default=datetime.utcnow)
    module = Column(String(100), nullable=False)
    error_trace = Column(Text, nullable=False)
    context_ticker = Column(String(30), nullable=True)


def log_ideas_error(module: str, error_trace: str, context_ticker: str | None = None) -> None:
    """Write a diagnostic error row to ideas_error_logs. Non-fatal — swallows its own errors."""
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


# ---------------------------------------------------------------------------
# Password hashing
# ---------------------------------------------------------------------------

def _hash_password(password: str) -> str:
    salt = bcrypt.gensalt(rounds=12)
    return bcrypt.hashpw(password.encode(), salt).decode()


def verify_password(plain: str, hashed: str) -> bool:
    try:
        if hashed.startswith("$2"):
            return bcrypt.checkpw(plain.encode(), hashed.encode())
        if ":" in hashed and len(hashed.split(":")[0]) == 32:
            salt, expected = hashed.split(":", 1)
            actual = hashlib.sha256((salt + plain).encode()).hexdigest()
            return secrets.compare_digest(actual, expected)
        # plain SHA-256 (legacy, no salt)
        actual = hashlib.sha256(plain.encode()).hexdigest()
        return secrets.compare_digest(actual, hashed)
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Seed data
# ---------------------------------------------------------------------------

# username → (display_name, password)
SEED_USERS = [
    ("saumya", "Saumya",  "123"),
    ("nirav",  "Nirav",   "123"),   # Dad — has the portfolio
    ("ankur",  "Ankur",   "123"),
]

DAD_HOLDINGS = [
    ("BGRENERGY",  "BGR Energy Systems Ltd",         6314,   162.00),
    ("MCLEODRUSS", "McLeod Russel India Ltd",         7000,   48.52),
    ("JITFINFRA",  "JITF Infralogistics Ltd",           496,    317.72),
    ("CDSL",       "Central Depository Services",     300,    1530.00),
    ("GAUDIUMIVF", "Gaudium IVF and Women Health Ltd",500,    120.00),
    ("SBIN",       "State Bank of India",             290,    1063.00),
    ("TATAELXSI",  "Tata Elxsi Ltd",                  25,     5533.00),
    ("OMPOWER",    "OM Power Trans Ltd",              600,    186.00),
    ("AVANTEL",    "Avantel Ltd",                     1400,   143.00),
    ("ABBOTINDIA", "Abbott India Ltd",                5,      25982.00),
    ("SUZLON",     "Suzlon Energy Ltd",               12000,  46.35),
    ("POLYCAB",    "Polycab India Ltd",               33,     8097.00),
    ("HAL",        "Hindustan Aeronautics Ltd",       100,    3922.00),
    ("IDEA",       "Vodafone Idea Ltd",               65000,  12.00),
    ("APOLLO",     "Apollo Microsystems Ltd",         1800,   232.00),
    ("BSE",        "BSE Ltd",                         375,    1210.00),
]


def _ensure_analysis_history_columns() -> None:
    """Idempotently migrate legacy SQLite/PostgreSQL analysis_history columns."""
    columns: dict[str, str] = {
        "raw_output": "TEXT",
        "scan_type": "VARCHAR(20) NOT NULL DEFAULT 'standard'",
        "promoter_pledged_pct": "FLOAT",
        "promoter_pledged_trend": "VARCHAR(20)",
        "outcome_delta_pct": "FLOAT",
        "was_correct": "BOOLEAN",
        "outcome_checked_at": "DATETIME",
        "market_regime": "VARCHAR DEFAULT 'Transition'",
        "calibrated_confidence": "FLOAT DEFAULT 0.0",
        "confidence_math_breakdown": "JSON DEFAULT '{}'",
        "conformal_target_upper_3m": "FLOAT",
        "conformal_target_lower_3m": "FLOAT",
        "quantitative_drivers": "JSON DEFAULT '{}'",
        "tail_risk_flags": "JSON DEFAULT '{}'",
    }
    dialect = ENGINE.dialect.name
    with ENGINE.begin() as connection:
        if dialect == "sqlite":
            existing = {
                row[1]
                for row in connection.exec_driver_sql(
                    "PRAGMA table_info(analysis_history)"
                ).fetchall()
            }
            for column_name, column_type in columns.items():
                if column_name not in existing:
                    connection.execute(
                        text(
                            f"ALTER TABLE analysis_history "
                            f"ADD COLUMN {column_name} {column_type}"
                        )
                    )
            return

        for column_name, column_type in columns.items():
            connection.execute(
                text(
                    f"ALTER TABLE analysis_history "
                    f"ADD COLUMN IF NOT EXISTS {column_name} {column_type}"
                )
            )


def init_db() -> None:
    Base.metadata.create_all(ENGINE)
    _ensure_analysis_history_columns()

    with get_session() as session:
        if session.query(User).count() > 0:
            return  # already seeded

        users_created = []
        for username, display_name, password in SEED_USERS:
            u = User(
                username=username,
                password_hash=_hash_password(password),
                display_name=display_name,
            )
            session.add(u)
            users_created.append(u)
        session.flush()

        nirav = next(u for u in users_created if u.username == "nirav")

        holdings = [
            Portfolio(
                user_id=nirav.id,
                ticker=ticker,
                company_name=company,
                shares=shares,
                buy_price=buy_price,
                group_name="holdings",
            )
            for ticker, company, shares, buy_price in DAD_HOLDINGS
        ]
        session.add_all(holdings)
        session.commit()
        print(f"[DB] Seeded users: {[u.username for u in users_created]}")
        print(f"[DB] Seeded {len(holdings)} holdings for nirav (user_id={nirav.id})")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

@contextmanager
def get_session() -> Session:
    session = SessionLocal()
    try:
        yield session
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def get_user_by_credentials(session: Session, username: str, password: str) -> Optional[User]:
    user = session.query(User).filter_by(username=username.lower().strip()).first()
    if user and verify_password(password, user.password_hash):
        return user
    return None


def save_analysis(session: Session, user_id: Optional[int], ticker: str, result: dict, raw_output: Optional[str] = None, scan_type: str = "standard") -> dict:
    """Save analysis. Returns result dict enriched with signal_changed and previous_signal."""
    ticker = ticker.upper()
    tp = result.get("target_prices") or {}
    new_signal = result.get("signal", "UNKNOWN")
    
    fundamentals = result.get("fundamentals_snapshot") or {}
    curr_pledged = fundamentals.get("promoter_pledged_pct")
    curr_pledged_trend = fundamentals.get("promoter_pledged_trend")

    # Intentionally cross-user: signal is market-wide; compare against latest analysis
    # for this ticker regardless of which user triggered it.
    prev_row = (
        session.query(AnalysisHistory)
        .filter(AnalysisHistory.ticker == ticker)
        .order_by(AnalysisHistory.created_at.desc())
        .first()
    )
    prev_signal = prev_row.signal if prev_row else None
    flipped = prev_signal is not None and prev_signal != new_signal
    
    # Promoter pledging increase logic (>5 percentage points)
    pledging_increased_warning = False
    if curr_pledged is not None and prev_row and prev_row.promoter_pledged_pct is not None:
        if (curr_pledged - prev_row.promoter_pledged_pct) > 5.0:
            flipped = True # Force signal_changed
            pledging_increased_warning = True
            
    if pledging_increased_warning:
        wtw = result.get("what_to_watch", [])
        if not any("PLEDGING INCREASED" in x for x in wtw):
            wtw.insert(0, "⚠ PLEDGING INCREASED: Significant jump in promoter pledging detected.")
            result["what_to_watch"] = wtw

    if flipped:
        session.add(SignalEvent(
            ticker=ticker,
            from_signal=prev_signal or "NONE",
            to_signal=new_signal,
            event_date=result.get("analysis_date", date.today().isoformat()),
        ))

    record = AnalysisHistory(
        user_id=user_id,
        ticker=ticker,
        analysis_date=date.today().isoformat(),  # always server date — never trust LLM's date field
        signal=new_signal,
        confidence_pct=result.get("confidence_pct"),
        target_short=tp.get("short_term_3m"),
        target_medium=tp.get("medium_term_12m"),
        target_long=tp.get("long_term_36m"),
        promoter_pledged_pct=curr_pledged,
        promoter_pledged_trend=curr_pledged_trend,
        raw_output=raw_output,
        full_json=json.dumps(result),
        scan_type=scan_type,
        # ML Hybrid Pipeline fields
        market_regime=result.get("market_regime", "Transition"),
        calibrated_confidence=result.get("calibrated_confidence", 0.0),
        confidence_math_breakdown=result.get("confidence_math_breakdown", {}),
        conformal_target_upper_3m=result.get("conformal_target_upper_3m"),
        conformal_target_lower_3m=result.get("conformal_target_lower_3m"),
        quantitative_drivers=result.get("quantitative_drivers", {}),
        tail_risk_flags=result.get("tail_risk_flags", {}),
    )
    session.add(record)
    session.commit()

    result["signal_changed"] = flipped
    result["previous_signal"] = prev_signal
    return result


def get_recent_analyses(
    session: Session, user_id: Optional[int], ticker: str, limit: int = 3
) -> list[dict]:
    q = session.query(AnalysisHistory).filter(AnalysisHistory.ticker == ticker)
    if user_id is not None:
        q = q.filter(AnalysisHistory.user_id == user_id)
    rows = q.order_by(AnalysisHistory.created_at.desc()).limit(limit).all()
    return [json.loads(r.full_json) for r in reversed(rows)]


def get_analysis_for_date(session: Session, ticker: str, target_date: str, scan_type: str = "standard") -> Optional[dict]:
    """Return the last analysis for ticker+scan_type regardless of date.
    Includes _staleness_hours, _staleness_label, _staleness_score, and _staleness_urgency."""
    from datetime import datetime as _dt, timezone as _tz
    from services.staleness import compute_staleness as _cs
    row = (
        session.query(AnalysisHistory)
        .filter(
            AnalysisHistory.ticker == ticker.upper(),
            AnalysisHistory.scan_type == scan_type,
        )
        .order_by(AnalysisHistory.created_at.desc())
        .first()
    )
    if not row:
        return None
    res = json.loads(row.full_json)
    res.setdefault("confidence_math_breakdown", row.confidence_math_breakdown or {})
    res["raw_output"] = row.raw_output
    res["_cached_scan_type"] = scan_type
    if row.created_at:
        result = _cs(
            last_analysis_date=row.created_at,
            price_change_7d_pct=float(res.get("7d_price_change_pct", 0) or 0),
            signal=res.get("signal", "HOLD") or "HOLD",
        )
        res["_staleness_hours"] = round(
            (_dt.now(_tz.utc) - row.created_at.replace(tzinfo=_tz.utc)).total_seconds() / 3600, 1
        )
        res["_staleness_label"] = result["urgency"].title()
        res["_staleness_score"] = result["score"]
        res["_staleness_urgency"] = result["urgency"]
        res["_staleness_reason"] = result["reason"]
    return res


def get_last_analysis_any_type(session: Session, ticker: str) -> Optional[dict]:
    """Return the most recent analysis for a ticker across all scan types.
    Priority: extreme > deep > standard. Returns analysis dict or None."""
    from datetime import datetime as _dt, timezone as _tz
    from services.staleness import compute_staleness as _cs
    for scan in ("extreme", "deep", "standard"):
        row = (
            session.query(AnalysisHistory)
            .filter(
                AnalysisHistory.ticker == ticker.upper(),
                AnalysisHistory.scan_type == scan,
            )
            .order_by(AnalysisHistory.created_at.desc())
            .first()
        )
        if row:
            res = json.loads(row.full_json)
            res.setdefault("confidence_math_breakdown", row.confidence_math_breakdown or {})
            res["raw_output"] = row.raw_output
            res["_cached_scan_type"] = scan
            if row.created_at:
                result = _cs(
                    last_analysis_date=row.created_at,
                    price_change_7d_pct=float(res.get("7d_price_change_pct", 0) or 0),
                    signal=res.get("signal", "HOLD") or "HOLD",
                )
                res["_staleness_hours"] = round(
                    (_dt.now(_tz.utc) - row.created_at.replace(tzinfo=_tz.utc)).total_seconds() / 3600, 1
                )
                res["_staleness_label"] = result["urgency"].title()
                res["_staleness_score"] = result["score"]
                res["_staleness_urgency"] = result["urgency"]
                res["_staleness_reason"] = result["reason"]
            return res
    return None


def get_all_ticker_history(session: Session, ticker: str, user_id: Optional[int] = None) -> list[dict]:
    q = session.query(AnalysisHistory).filter(AnalysisHistory.ticker == ticker.upper())
    if user_id is not None:
        q = q.filter(AnalysisHistory.user_id == user_id)
    rows = q.order_by(AnalysisHistory.created_at.asc()).all()
    results = []
    for r in rows:
        res = json.loads(r.full_json)
        res.setdefault("confidence_math_breakdown", r.confidence_math_breakdown or {})
        res["raw_output"] = r.raw_output
        results.append(res)
    return results


# ---------------------------------------------------------------------------
# AnalysisJob DAO — self-managing sessions (called from routers + worker subprocess).
# These open their own get_session() and commit, unlike the *_analysis helpers above
# which take a caller-provided session.
# ---------------------------------------------------------------------------

_JOB_TERMINAL = {"SUCCEEDED", "FAILED", "CANCELLED", "TIMEOUT"}


def _job_to_dict(j: "AnalysisJob") -> dict:
    return {
        "job_id": j.job_id, "user_id": j.user_id, "ticker": j.ticker,
        "exchange": j.exchange, "scan_type": j.scan_type, "status": j.status,
        "stage": j.stage, "progress_pct": j.progress_pct,
        "checkpoints": json.loads(j.checkpoints or "[]"),
        "pid": j.pid, "tokens_used": j.tokens_used, "error": j.error,
        "created_at": j.created_at.isoformat() if j.created_at else None,
        "started_at": j.started_at.isoformat() if j.started_at else None,
        "finished_at": j.finished_at.isoformat() if j.finished_at else None,
    }


def create_job(user_id: Optional[int], ticker: str, exchange: str, scan_type: str) -> dict:
    jid = str(uuid.uuid4())[:12]
    with get_session() as s:
        j = AnalysisJob(job_id=jid, user_id=user_id, ticker=ticker.upper(),
                        exchange=exchange, scan_type=scan_type, status="QUEUED",
                        heartbeat_at=datetime.utcnow())
        s.add(j)
        s.commit()
        return _job_to_dict(j)


def get_job(job_id: str) -> Optional[dict]:
    with get_session() as s:
        j = s.get(AnalysisJob, job_id)
        if not j:
            return None
        d = _job_to_dict(j)
        if j.status == "SUCCEEDED" and j.result_json:
            try:
                d["result"] = json.loads(j.result_json)
            except Exception:
                d["result"] = None
        return d


def update_job(job_id: str, **fields) -> None:
    if fields.get("status") in _JOB_TERMINAL:
        fields.setdefault("finished_at", datetime.utcnow())
    if fields.get("status") == "RUNNING":
        fields.setdefault("started_at", datetime.utcnow())
    fields.setdefault("heartbeat_at", datetime.utcnow())
    with get_session() as s:
        j = s.get(AnalysisJob, job_id)
        if not j:
            return
        for k, v in fields.items():
            setattr(j, k, v)
        s.commit()


def append_checkpoint(job_id: str, *, stage: str, agent: str,
                      message: str, state: str, pct: int) -> None:
    with get_session() as s:
        j = s.get(AnalysisJob, job_id)
        if not j:
            return
        cps = json.loads(j.checkpoints or "[]")
        cps.append({"ts": datetime.utcnow().isoformat(), "stage": stage,
                    "agent": agent, "message": message, "state": state})
        j.checkpoints = json.dumps(cps, ensure_ascii=False)
        j.stage = stage
        j.progress_pct = max(j.progress_pct or 0, int(pct))
        j.heartbeat_at = datetime.utcnow()
        s.commit()


def add_job_tokens(job_id: str, n: int) -> int:
    with get_session() as s:
        j = s.get(AnalysisJob, job_id)
        if not j:
            return 0
        j.tokens_used = (j.tokens_used or 0) + int(n)
        j.heartbeat_at = datetime.utcnow()
        s.commit()
        return j.tokens_used


def get_active_job_for_user(user_id: Optional[int]) -> Optional[dict]:
    if user_id is None:
        return None
    with get_session() as s:
        j = (s.query(AnalysisJob)
               .filter(AnalysisJob.user_id == user_id,
                       AnalysisJob.status.in_(["QUEUED", "RUNNING"]))
               .order_by(AnalysisJob.created_at.desc()).first())
        return _job_to_dict(j) if j else None


# Wall-clock limits mirror services.job_worker._WALLCLOCK_LIMITS so a crashed
# worker never permanently blocks new runs of the same scan_type.
_STALE_LIMITS: dict[str, int] = {"extreme": 600, "deep": 420, "standard": 300}


def get_active_job_for_user_and_type(user_id: Optional[int], scan_type: str) -> Optional[dict]:
    """Active (QUEUED/RUNNING) job for this user AND scan_type, ignoring stale
    jobs older than their wall-clock limit. Lets extreme and standard coexist."""
    if user_id is None:
        return None
    cutoff_sec = _STALE_LIMITS.get(scan_type, 300)
    threshold = datetime.utcnow() - timedelta(seconds=cutoff_sec)
    with get_session() as s:
        j = (s.query(AnalysisJob)
               .filter(AnalysisJob.user_id == user_id,
                       AnalysisJob.scan_type == scan_type,
                       AnalysisJob.status.in_(["QUEUED", "RUNNING"]),
                       AnalysisJob.created_at >= threshold)
               .order_by(AnalysisJob.created_at.desc()).first())
        return _job_to_dict(j) if j else None


def list_active_jobs() -> list[dict]:
    """All QUEUED/RUNNING jobs — for the live dashboard 'what's running' panel."""
    with get_session() as s:
        rows = (s.query(AnalysisJob)
                  .filter(AnalysisJob.status.in_(["QUEUED", "RUNNING"]))
                  .order_by(AnalysisJob.created_at.desc()).all())
        return [_job_to_dict(j) for j in rows]


def sweep_stale_jobs(max_heartbeat_age_sec: int = 90) -> int:
    """Crash recovery: mark QUEUED/RUNNING jobs with a stale heartbeat as FAILED."""
    cutoff = datetime.utcnow() - timedelta(seconds=max_heartbeat_age_sec)
    with get_session() as s:
        stale = (s.query(AnalysisJob)
                   .filter(AnalysisJob.status.in_(["QUEUED", "RUNNING"]),
                           AnalysisJob.heartbeat_at < cutoff).all())
        for j in stale:
            j.status = "FAILED"
            j.error = "Worker died (stale heartbeat / server restart)"
            j.finished_at = datetime.utcnow()
        s.commit()
        return len(stale)


def create_user(session: Session, username: str, password: str, display_name: str) -> Optional[User]:
    try:
        password_hash = _hash_password(password)
        user = User(username=username.lower(), password_hash=password_hash, display_name=display_name)
        session.add(user)
        session.commit()
        return user
    except Exception:
        session.rollback()
        return None


# ---------------------------------------------------------------------------
# JWT Authentication
# ---------------------------------------------------------------------------

import jwt as pyjwt
import threading

_JWT_SECRET = os.getenv("JWT_SECRET", secrets.token_hex(32))
_JWT_ALGORITHM = "HS256"
_JWT_EXPIRY_HOURS = 720  # 30 days — prevents silent 401s from expired tokens on mobile
_admin_lock = threading.Lock()
_admin_users: set[int] = set()


def create_access_token(user_id: int) -> str:
    payload = {
        "sub": str(user_id),
        "iat": datetime.utcnow(),
        "exp": datetime.utcnow() + timedelta(hours=_JWT_EXPIRY_HOURS),
    }
    return pyjwt.encode(payload, _JWT_SECRET, algorithm=_JWT_ALGORITHM)


def verify_access_token(token: str) -> Optional[int]:
    try:
        payload = pyjwt.decode(token, _JWT_SECRET, algorithms=[_JWT_ALGORITHM])
        sub = payload.get("sub")
        return int(sub) if sub is not None else None
    except Exception:
        return None


def set_admin(user_id: int) -> None:
    with _admin_lock:
        _admin_users.add(user_id)


def is_admin(user_id: int) -> bool:
    with _admin_lock:
        return user_id in _admin_users


def promote_initial_admins() -> None:
    with get_session() as session:
        admins = session.query(User).filter(User.username.in_(["saumya", "nirav"])).all()
        for u in admins:
            _admin_users.add(u.id)
