"""SQLite / PostgreSQL database setup and session management.

Handles database engine initialization, SQLAlchemy session dependency generation,
and basic CRUD operations that don't belong to a specific domain repository.
"""

from __future__ import annotations

import functools
import hashlib
import json
import logging
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
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

# ---------------------------------------------------------------------------
# Environment-aware engine — SQLite locally, PostgreSQL on DigitalOcean
# ---------------------------------------------------------------------------

_DEFAULT_SQLITE = f"sqlite:///{Path(__file__).parent / 'stockapp.db'}"
DATABASE_URL = os.getenv("DATABASE_URL", _DEFAULT_SQLITE)


def _pg_connect_args() -> dict:
    """Server-side timeouts for every Postgres connection (DB-22).

    statement_timeout bounds a hung query; idle_in_transaction_session_timeout
    ends a session left idle inside an open transaction, so it cannot pin a
    pooled connection or the vacuum horizon. Both are in ms, env-overridable.
    timezone=UTC (DB-24): naive DateTime columns hold UTC, so aware UTC values must not
    be shifted into the server/role TimeZone on write.
    """
    statement_ms = int(os.getenv("DB_STATEMENT_TIMEOUT_MS", "60000"))
    idle_tx_ms = int(os.getenv("DB_IDLE_TX_TIMEOUT_MS", "120000"))
    return {
        "options": f"-c statement_timeout={statement_ms} -c idle_in_transaction_session_timeout={idle_tx_ms} -c timezone=UTC"
    }


if DATABASE_URL.startswith("postgresql"):
    # Task 48: improved connection pool settings
    ENGINE = create_engine(
        DATABASE_URL,
        pool_size=10,
        max_overflow=20,
        pool_timeout=10,
        pool_pre_ping=True,
        pool_recycle=3600,
        connect_args=_pg_connect_args(),
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
        dbapi_conn.execute("PRAGMA wal_autocheckpoint=100")  # Fixes #129: keep WAL small

SessionLocal = sessionmaker(bind=ENGINE, autoflush=False, autocommit=False)


def _reset_pool_after_fork() -> None:
    """DB-02: a forked child must never reuse the parent's pooled sockets.

    dispose(close=False) drops the inherited pool without closing the parent's
    connections; the child then opens its own on first use.
    """
    ENGINE.dispose(close=False)


if hasattr(os, "register_at_fork"):
    os.register_at_fork(after_in_child=_reset_pool_after_fork)


@contextmanager
def get_session() -> Session:
    """Provide a transactional scope around a series of operations.
    
    Yields:
        Session: SQLAlchemy session object.
    
    Raises:
        Exception: Re-raises any exception after rolling back the transaction.
    """
    session = SessionLocal()
    try:
        yield session
    except Exception as _e:
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
    NetWorthLedger, MarketErrorLog, EarningsAlert,
    EarningsErrorLog, BlockDeal, FIIDIIFlow,
    NotificationErrorLog, AdvisorBiography,
    TextAdvisoryInsight, IdeasErrorLog, PortfolioTransaction,
)

# ---------------------------------------------------------------------------
# Telemetry error-log helpers (GH-610: moved here from models/db_models.py)
# ---------------------------------------------------------------------------

_telemetry_log = logging.getLogger("nivesh.telemetry")


def _write_error_row(model_cls, text_field: str, text, **fields) -> None:
    """Insert one diagnostic row. Never raises: telemetry must not cascade.

    A failed write is logged at WARNING instead of vanishing silently.
    """
    # ponytail: no rate limiting; add it if a DB outage floods the logs.
    try:
        with get_session() as session:
            session.add(model_cls(**{text_field: str(text)[:2000]}, **fields))
            session.commit()
    except Exception:
        _telemetry_log.warning("telemetry write to %s failed", model_cls.__tablename__, exc_info=True)


def log_market_error(component: str, error_message: str, context_ticker: str | None = None) -> None:
    """Write a diagnostic error row to market_error_logs. Non-fatal."""
    _write_error_row(MarketErrorLog, "error_message", error_message, component=component, context_ticker=context_ticker)


def log_earnings_error(module: str, error_trace: str, failed_ticker: str | None = None) -> None:
    """Write a diagnostic error row to earnings_error_logs. Non-fatal."""
    _write_error_row(EarningsErrorLog, "error_trace", error_trace, module=module, failed_ticker=failed_ticker)


def log_notification_error(failure_point: str, error_trace: str, target_device: str | None = None) -> None:
    """Write a diagnostic error row to notification_error_logs. Non-fatal."""
    _write_error_row(NotificationErrorLog, "error_trace", error_trace, failure_point=failure_point, target_device=target_device)


def log_ideas_error(module: str, error_trace: str, context_ticker: str | None = None) -> None:
    """Write a diagnostic error row to ideas_error_logs. Non-fatal."""
    _write_error_row(IdeasErrorLog, "error_trace", error_trace, module=module, context_ticker=context_ticker)

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
    
    Args:
        ticker (str): The stock ticker symbol to validate.
        
    Returns:
        str: The validated and cleaned ticker symbol.
        
    Raises:
        ValueError: If the ticker is empty, too long, or invalid.
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
    """Hash a plaintext password using bcrypt.
    
    Args:
        password (str): The plaintext password to hash.
        
    Returns:
        str: The bcrypt hash string.
    """
    salt = bcrypt.gensalt(rounds=12)
    return bcrypt.hashpw(password.encode(), salt).decode()


def verify_password(plain: str, hashed: str) -> bool:
    """Verify a plaintext password against a hash.
    
    Args:
        plain (str): The plaintext password.
        hashed (str): The expected hash (bcrypt or SHA-256).
        
    Returns:
        bool: True if the password matches, False otherwise.
    """
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
    except Exception as _e:
        return False


@functools.cache
def _dummy_hash() -> str:
    """A cost-12 bcrypt hash checked for unknown usernames, so login time does not reveal them (AUTH-23)."""
    return _hash_password(secrets.token_hex(16))


def init_db() -> None:
    """Create any missing tables (development/test only). Seeds nothing (AUTH-01).

    In development/test, creates all tables if they don't exist; any other
    environment gets its schema only from `alembic upgrade head` (DB-07), so
    create_all can't paper over a missing migration.

    Accounts come only from /register; admin rights only from
    `scripts/manage_users.py set-admin`. Dev data:
    `ENVIRONMENT=development scripts/reset_mock_user.py --yes`.
    """
    from core.config_guard import is_production
    if not is_production():
        Base.metadata.create_all(ENGINE)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def get_user_by_credentials(session: Session, username: str, password: str) -> Optional[User]:
    """Retrieve a user by verifying their credentials.
    
    Args:
        session (Session): The database session.
        username (str): The user's username.
        password (str): The plaintext password to verify.
        
    Returns:
        Optional[User]: The matching user if credentials are valid, None otherwise.
    """
    user = session.query(User).filter_by(username=username.lower().strip()).first()
    if user is None:
        verify_password(password, _dummy_hash())  # same bcrypt work as a real account
        return None
    if not verify_password(password, user.password_hash):
        return None
    if not str(user.password_hash).startswith("$2"):
        # AUTH-23: upgrade a legacy SHA-256 hash to bcrypt on its first good login.
        session.query(User).filter_by(id=user.id).update({"password_hash": _hash_password(password)})
        session.commit()
    return user


def get_last_analysis_any_type(session: Session, ticker: str) -> Optional[dict]:
    """Return the most recent analysis for a ticker across all scan types.
    
    Priority: extreme > deep > standard.
    
    Args:
        session (Session): The database session.
        ticker (str): The stock ticker symbol.
        
    Returns:
        Optional[dict]: The most recent analysis as a dictionary, or None.
    """
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
    """Create a new user in the database.
    
    Args:
        session (Session): The database session.
        username (str): The username for the new account.
        password (str): The plaintext password.
        display_name (str): The display name for the user.
        
    Returns:
        Optional[User]: The created User object, or None if creation failed.
    """
    try:
        password_hash = _hash_password(password)
        # Same normalisation as get_user_by_credentials, or the account can never log in (AUTH-23).
        user = User(username=username.strip().lower(), password_hash=password_hash, display_name=display_name)
        session.add(user)
        session.commit()
        return user
    except IntegrityError:
        session.rollback()
        raise ValueError("Username already exists")
    except Exception as _e:
        session.rollback()
        return None


# ---------------------------------------------------------------------------
# JWT Authentication
# ---------------------------------------------------------------------------

import logging  # noqa: E402

import jwt as pyjwt  # noqa: E402

_auth_logger = logging.getLogger("nivesh.auth")


def _load_jwt_secret(env=os.environ) -> str:
    """JWT_SECRET, refusing a missing/weak value in production (SILENT-09).

    Outside production a weak value falls back to a per-process random secret and
    logs CRITICAL, because such tokens die on restart and fail on other workers.
    """
    from core.config_guard import is_production, jwt_secret_problem
    secret = env.get("JWT_SECRET")
    problem = jwt_secret_problem(secret)
    if problem is None:
        return str(secret)
    if is_production(env):
        raise RuntimeError(f"{problem}: JWT_SECRET must be set (>=32 chars) in production")
    _auth_logger.critical(
        "%s - using a per-process random secret; tokens will not survive restarts "
        "or work across workers", problem,
    )
    return secrets.token_hex(32)


_JWT_SECRET = _load_jwt_secret()
_JWT_ALGORITHM = "HS256"
# 30 days, but revocable: logout / password change bump users.token_version (AUTH-13).
# ponytail: long-lived token, add short access + refresh tokens once iOS has central 401 handling.
_JWT_EXPIRY_HOURS = 720


def create_access_token(user_id: int, token_version: int = 0) -> str:
    """Create a JWT access token for authentication.
    
    Args:
        user_id (int): The ID of the user.
        token_version (int): The user's current users.token_version; the token
            stops verifying once that column is bumped (AUTH-13).
        
    Returns:
        str: The encoded JWT token.
    """
    payload = {
        "sub": str(user_id),
        "ver": int(token_version or 0),
        "iat": datetime.now(timezone.utc),
        "exp": datetime.now(timezone.utc) + timedelta(hours=_JWT_EXPIRY_HOURS),
    }
    return pyjwt.encode(payload, _JWT_SECRET, algorithm=_JWT_ALGORITHM)


def verify_access_token(token: str) -> Optional[int]:
    """Verify a JWT access token and return the user ID.
    
    Args:
        token (str): The JWT token to verify.
        
    Returns:
        Optional[int]: The user ID if token is valid, None otherwise.
    """
    try:
        payload = pyjwt.decode(token, _JWT_SECRET, algorithms=[_JWT_ALGORITHM])
        sub = payload.get("sub")
        if sub is None:
            return None
        user_id = int(sub)
        # AUTH-13: revoked by logout/password change/erasure (token_version bump) or
        # unknown user. Tokens minted before the "ver" claim count as version 0.
        # FINSEC-03: an erased account keeps a tombstone row; its tokens die with it.
        with get_session() as session:
            row = session.query(User.token_version, User.deleted_at).filter(User.id == user_id).first()
        if row is None or row[1] is not None or int(payload.get("ver", 0)) != int(row[0]):
            _auth_logger.debug("[auth] revoked, erased or unknown-user token")
            return None
        return user_id
    except pyjwt.ExpiredSignatureError:
        _auth_logger.debug("[auth] token expired")
    except pyjwt.InvalidSignatureError:
        _auth_logger.warning("[auth] invalid token signature (secret mismatch across workers/restarts?)")
    except (pyjwt.InvalidTokenError, ValueError, TypeError):
        _auth_logger.debug("[auth] malformed token")
    return None


def is_admin(user_id: int) -> bool:
    """Check if a user has admin privileges.

    Reads the persisted users.is_admin flag on every call (set only by
    scripts/manage_users.py), so every worker agrees and revocation is immediate.
    Never derived from the username.

    Args:
        user_id (int): The user ID to check.

    Returns:
        bool: True if the user exists and is an admin, False otherwise.
    """
    with get_session() as session:
        return bool(session.query(User.is_admin).filter(User.id == user_id).scalar())

# ---------------------------------------------------------------------------
# Repository re-exports (bottom of file to avoid circular imports)
# ---------------------------------------------------------------------------
from repositories.analysis_repo import (
    save_analysis, get_recent_analyses, get_analysis_for_date, get_all_ticker_history,
    latest_per_ticker,
)
from repositories.job_repo import (
    create_job, get_job, update_job, append_checkpoint, add_job_tokens,
    get_active_job_for_user, get_active_job_for_user_and_type,
    list_active_jobs, sweep_stale_jobs,
)
