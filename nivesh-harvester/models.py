"""
Nivesh Harvester — SQLAlchemy models + DB lifecycle.

Completely separate from the main backend's database. Uses its own SQLite
file (`harvester.db`) in this directory. If this database is corrupted or the
harvester crashes, the main Nivesh backend (port 8000, stockapp.db) is
unaffected — zero overlap by design.

Two tables:
  HarvestedCard  — one reformatted, credibility-scored card per scraped item.
  SourceHealth   — per-source scrape health for the /harvester/sources endpoint.

Public API:
  init_db()                          — create tables (idempotent).
  get_session()                      — context manager (commit/rollback/close).
  SessionLocal                       — raw session factory (for manual use).
  upsert_card(session, card)         — insert if external_id is new; True if inserted.
  record_source_health(...)          — upsert a SourceHealth row.
"""

from __future__ import annotations

import json
import os
from contextlib import contextmanager
from datetime import datetime

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Integer,
    String,
    Text,
    create_engine,
)
from sqlalchemy.orm import declarative_base, sessionmaker

# ── DB location: always next to this file, never shared with the backend ──────
_DB_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(_DB_DIR, "harvester.db")
DATABASE_URL = f"sqlite:///{DB_PATH}"

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},  # APScheduler threads + FastAPI
    future=True,
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
Base = declarative_base()


# ═════════════════════════════════════════════════════════════════════════════
# Tables
# ═════════════════════════════════════════════════════════════════════════════

class HarvestedCard(Base):
    __tablename__ = "harvested_cards"

    id = Column(Integer, primary_key=True, autoincrement=True)
    # Deterministic hash of (url + content). Guarantees dedup across runs.
    external_id = Column(String(64), unique=True, index=True, nullable=False)

    source_type = Column(String(40), index=True, nullable=False)
    source_name = Column(String(120), nullable=False, default="")
    source_url = Column(Text, nullable=False, default="")
    original_author = Column(String(200), nullable=True)
    published_at = Column(DateTime, nullable=True, index=True)

    title = Column(Text, nullable=False, default="")
    raw_text = Column(Text, nullable=False, default="")

    reformatted_summary = Column(Text, nullable=True)
    key_takeaways = Column(Text, nullable=True)   # JSON-encoded list[str]
    tickers = Column(Text, nullable=True)         # JSON-encoded list[str]
    sentiment = Column(String(12), nullable=True)  # BULLISH / BEARISH / NEUTRAL

    credibility_score = Column(Integer, nullable=False, default=5, index=True)
    card_type = Column(String(20), index=True, nullable=False, default="EXPERT")
    expert_credential = Column(Text, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow, index=True)

    def to_dict(self) -> dict:
        """Serialize for the REST API. snake_case keys (iOS decodes them)."""
        def _loads(raw):
            if not raw:
                return []
            try:
                val = json.loads(raw)
                return val if isinstance(val, list) else []
            except Exception:
                return []

        return {
            "id": self.id,
            "source_type": self.source_type,
            "source_name": self.source_name,
            "source_url": self.source_url,
            "original_author": self.original_author,
            "published_at": self.published_at.isoformat() if self.published_at else None,
            "title": self.title,
            "reformatted_summary": self.reformatted_summary,
            "key_takeaways": _loads(self.key_takeaways),
            "tickers": _loads(self.tickers),
            "sentiment": self.sentiment,
            "credibility_score": self.credibility_score,
            "card_type": self.card_type,
            "expert_credential": self.expert_credential,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class SourceHealth(Base):
    __tablename__ = "source_health"

    id = Column(Integer, primary_key=True, autoincrement=True)
    source_name = Column(String(120), unique=True, index=True, nullable=False)
    last_success = Column(DateTime, nullable=True)
    last_failure = Column(DateTime, nullable=True)
    error_message = Column(Text, nullable=True)
    items_scraped = Column(Integer, nullable=False, default=0)
    is_healthy = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    def to_dict(self) -> dict:
        return {
            "source_name": self.source_name,
            "last_success": self.last_success.isoformat() if self.last_success else None,
            "last_failure": self.last_failure.isoformat() if self.last_failure else None,
            "error_message": self.error_message,
            "items_scraped": self.items_scraped,
            "is_healthy": self.is_healthy,
        }


# ═════════════════════════════════════════════════════════════════════════════
# Lifecycle
# ═════════════════════════════════════════════════════════════════════════════

def init_db() -> None:
    """Create all tables. Safe to call repeatedly."""
    Base.metadata.create_all(bind=engine)


@contextmanager
def get_session():
    """Context-managed session: commits on success, rolls back on error."""
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


# ═════════════════════════════════════════════════════════════════════════════
# Helpers shared by every harvester + the scheduler
# ═════════════════════════════════════════════════════════════════════════════

# Cards below this score are REJECTED — never stored, never displayed.
MIN_CREDIBILITY = 5


def _coerce_int(value, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def upsert_card(session, card: dict) -> bool:
    """Insert a card if its external_id is not already present.

    `card` is a plain dict. Required: external_id, source_type, source_url.
    List fields (key_takeaways, tickers) may be either Python lists or
    already-JSON-encoded strings. Returns True iff a new row was inserted.

    Cards with credibility_score < MIN_CREDIBILITY are silently skipped.
    """
    ext_id = (card.get("external_id") or "").strip()
    if not ext_id:
        return False

    cred = _coerce_int(card.get("credibility_score"), 5)
    if cred < MIN_CREDIBILITY:
        return False

    existing = (
        session.query(HarvestedCard)
        .filter(HarvestedCard.external_id == ext_id)
        .first()
    )
    if existing:
        return False

    def _dump(val):
        if val is None:
            return None
        if isinstance(val, str):
            return val
        try:
            return json.dumps(val, ensure_ascii=False)
        except Exception:
            return None

    published = card.get("published_at")
    if isinstance(published, str):
        published = _parse_dt(published)

    row = HarvestedCard(
        external_id=ext_id,
        source_type=(card.get("source_type") or "EXPERT")[:40],
        source_name=(card.get("source_name") or "")[:120],
        source_url=card.get("source_url") or "",
        original_author=(card.get("original_author") or None),
        published_at=published if isinstance(published, datetime) else None,
        title=(card.get("title") or "")[:2000],
        raw_text=card.get("raw_text") or "",
        reformatted_summary=card.get("reformatted_summary"),
        key_takeaways=_dump(card.get("key_takeaways")),
        tickers=_dump(card.get("tickers")),
        sentiment=(card.get("sentiment") or None),
        credibility_score=cred,
        card_type=(card.get("card_type") or "EXPERT")[:20],
        expert_credential=card.get("expert_credential"),
        created_at=datetime.utcnow(),
    )
    session.add(row)
    return True


def record_source_health(
    session,
    source_name: str,
    *,
    success: bool,
    items: int = 0,
    error: str | None = None,
) -> None:
    """Upsert a SourceHealth row after each scrape attempt."""
    if not source_name:
        return
    row = (
        session.query(SourceHealth)
        .filter(SourceHealth.source_name == source_name)
        .first()
    )
    if not row:
        row = SourceHealth(source_name=source_name[:120], items_scraped=0)
        session.add(row)

    now = datetime.utcnow()
    if success:
        row.last_success = now
        row.is_healthy = True
        row.error_message = None
        row.items_scraped = (row.items_scraped or 0) + max(0, int(items or 0))
    else:
        row.last_failure = now
        row.is_healthy = False
        row.error_message = (error or "unknown error")[:500]


def _parse_dt(raw: str) -> datetime | None:
    """Best-effort parse of common feed/ISO date strings. Never raises."""
    if not raw:
        return None
    raw = str(raw).strip()
    # ISO first
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00")).replace(tzinfo=None)
    except Exception:
        pass
    for fmt in (
        "%a, %d %b %Y %H:%M:%S %z",
        "%a, %d %b %Y %H:%M:%S %Z",
        "%a, %d %b %Y %H:%M:%S",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d",
        "%d %b %Y",
        "%d-%m-%Y",
    ):
        try:
            return datetime.strptime(raw, fmt).replace(tzinfo=None)
        except Exception:
            continue
    return None
