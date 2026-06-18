"""SQLite / PostgreSQL database setup, session management, and seed data."""

from __future__ import annotations

import hashlib
import json
import os
import secrets
import bcrypt
from datetime import datetime, date, timedelta, timezone
from pathlib import Path
from typing import Optional
from contextlib import contextmanager

from sqlalchemy import (
    create_engine, event, text,
)
from sqlalchemy.orm import Session, sessionmaker

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
        dbapi_conn.execute("PRAGMA foreign_keys=ON")

SessionLocal = sessionmaker(bind=ENGINE, autoflush=False, autocommit=False)


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


# ---------------------------------------------------------------------------
# Import ORM models (moved to models/db_models.py)
# ---------------------------------------------------------------------------
from models.db_models import (  # noqa: E402
    Base, User, Portfolio, AnalysisHistory, SignalEvent, AnalysisJob,
    PriceTarget, TradeJournal, DeviceToken, AdvisorInsight, NewsArticle,
    YouTubeVideo, PortfolioValuationHistory, PKScreenerSignal, MacroEvent,
    NetWorthLedger, MarketErrorLog, EarningsAlert, log_market_error,
    EarningsErrorLog, log_earnings_error, BlockDeal, FIIDIIFlow,
    NotificationErrorLog, log_notification_error, AdvisorBiography,
    TextAdvisoryInsight, IdeasErrorLog, log_ideas_error,
)

# ---------------------------------------------------------------------------
# Ticker safety
# ---------------------------------------------------------------------------

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

# username -> (display_name, password)
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

def get_user_by_credentials(session: Session, username: str, password: str) -> Optional[User]:
    user = session.query(User).filter_by(username=username.lower().strip()).first()
    if user and verify_password(password, user.password_hash):
        return user
    return None


def get_last_analysis_any_type(session: Session, ticker: str) -> Optional[dict]:
    """Return the most recent analysis for a ticker across all scan types.
    Priority: extreme > deep > standard. Returns analysis dict or None."""
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
                    (datetime.now(timezone.utc) - row.created_at.replace(tzinfo=timezone.utc)).total_seconds() / 3600, 1
                )
                res["_staleness_label"] = result["urgency"].title()
                res["_staleness_score"] = result["score"]
                res["_staleness_urgency"] = result["urgency"]
                res["_staleness_reason"] = result["reason"]
            return res
    return None


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

import jwt as pyjwt  # noqa: E402
import threading

_JWT_SECRET = os.getenv("JWT_SECRET", secrets.token_hex(32))
_JWT_ALGORITHM = "HS256"
_JWT_EXPIRY_HOURS = 720  # 30 days — prevents silent 401s from expired tokens on mobile
_admin_lock = threading.Lock()
_admin_users: set[int] = set()


def create_access_token(user_id: int) -> str:
    payload = {
        "sub": str(user_id),
        "iat": datetime.now(timezone.utc),
        "exp": datetime.now(timezone.utc) + timedelta(hours=_JWT_EXPIRY_HOURS),
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

# ---------------------------------------------------------------------------
# Repository re-exports (bottom of file to avoid circular imports)
# ---------------------------------------------------------------------------
from repositories.analysis_repo import (
    save_analysis, get_recent_analyses, get_analysis_for_date, get_all_ticker_history,
)
from repositories.job_repo import (
    create_job, get_job, update_job, append_checkpoint, add_job_tokens,
    get_active_job_for_user, get_active_job_for_user_and_type,
    list_active_jobs, sweep_stale_jobs,
)
