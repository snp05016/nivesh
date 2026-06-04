"""SQLite / PostgreSQL database setup, models, and seed data."""

from __future__ import annotations

import hashlib
import json
import os
import secrets
import bcrypt
from datetime import datetime, date, timedelta
from pathlib import Path
from typing import Optional
from contextlib import contextmanager

from sqlalchemy import (
    Boolean, Column, DateTime, Float, Integer, String, Text,
    ForeignKey, Index, UniqueConstraint, create_engine, event,
)
from sqlalchemy.orm import DeclarativeBase, Session, relationship, sessionmaker

# ---------------------------------------------------------------------------
# Environment-aware engine — SQLite locally, PostgreSQL on DigitalOcean
# ---------------------------------------------------------------------------

_DEFAULT_SQLITE = f"sqlite:///{Path(__file__).parent / 'stockapp.db'}"
DATABASE_URL = os.getenv("DATABASE_URL", _DEFAULT_SQLITE)

if DATABASE_URL.startswith("postgresql"):
    ENGINE = create_engine(
        DATABASE_URL,
        pool_size=5,
        max_overflow=10,
        pool_pre_ping=True,   # detect dropped connections
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
    # Epistemic feedback loop — added 2026-06-03
    outcome_delta_pct    = Column(Float, nullable=True)   # % price change since analysis
    was_correct          = Column(Boolean, nullable=True)  # signal matched price direction
    outcome_checked_at   = Column(DateTime, nullable=True)
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


def init_db() -> None:
    Base.metadata.create_all(ENGINE)

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


def save_analysis(session: Session, user_id: Optional[int], ticker: str, result: dict, raw_output: Optional[str] = None) -> dict:
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
        analysis_date=result.get("analysis_date", date.today().isoformat()),
        signal=new_signal,
        confidence_pct=result.get("confidence_pct"),
        target_short=tp.get("short_term_3m"),
        target_medium=tp.get("medium_term_12m"),
        target_long=tp.get("long_term_36m"),
        promoter_pledged_pct=curr_pledged,
        promoter_pledged_trend=curr_pledged_trend,
        raw_output=raw_output,
        full_json=json.dumps(result),
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


def get_analysis_for_date(session: Session, ticker: str, target_date: str) -> Optional[dict]:
    row = session.query(AnalysisHistory).filter(
        AnalysisHistory.ticker == ticker.upper(),
        AnalysisHistory.analysis_date == target_date
    ).first()
    if not row: return None
    res = json.loads(row.full_json)
    res["raw_output"] = row.raw_output
    return res


def get_all_ticker_history(session: Session, ticker: str, user_id: Optional[int] = None) -> list[dict]:
    q = session.query(AnalysisHistory).filter(AnalysisHistory.ticker == ticker.upper())
    if user_id is not None:
        q = q.filter(AnalysisHistory.user_id == user_id)
    rows = q.order_by(AnalysisHistory.created_at.asc()).all()
    results = []
    for r in rows:
        res = json.loads(r.full_json)
        res["raw_output"] = r.raw_output
        results.append(res)
    return results


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
_JWT_EXPIRY_HOURS = 72
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
