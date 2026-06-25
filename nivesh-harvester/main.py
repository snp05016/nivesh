"""
Nivesh Harvester — FastAPI app (port 8001).

A completely separate microservice from the main Nivesh backend (port 8000).
Serves credibility-scored, reformatted cards scraped from credentialed expert
sources. If this service crashes, the main backend is unaffected.

Endpoints (all under /harvester):
  GET  /harvester/feed?ticker=&limit=        latest cards (optionally per ticker)
  GET  /harvester/governance/{ticker}        GOVERNANCE cards for a ticker
  GET  /harvester/sources                    per-source health
  GET  /harvester/search?q=                  full-text search
  POST /harvester/trigger/scrape?source=&limit=   manual scrape
  GET  /harvester/stats                      aggregate counts
  GET  /                                      service banner / liveness
"""

from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware

from models import HarvestedCard, SourceHealth, get_session, init_db
from scheduler import run_scrape, start_scheduler, stop_scheduler

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
)
logger = logging.getLogger("harvester.main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Nivesh Harvester starting up …")
    init_db()
    start_scheduler()
    logger.info("Nivesh Harvester ready on :8001")
    try:
        yield
    finally:
        logger.info("Nivesh Harvester shutting down …")
        stop_scheduler()


app = FastAPI(title="Nivesh Harvester", version="1.0.0", lifespan=lifespan)
# Fixes #117: Restrict CORS to configured origins (not wildcard)
_HV_ALLOWED_ORIGINS = [o.strip() for o in os.getenv("ALLOWED_ORIGINS", "").split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_HV_ALLOWED_ORIGINS or ["http://localhost:3000"],  # dev-only fallback
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


# ── helpers ───────────────────────────────────────────────────────────────────

def _ticker_filter(query, ticker: str):
    """Match cards whose tickers JSON contains the ticker OR whose title does."""
    t = ticker.upper().strip()
    like_json = f'%"{t}"%'
    like_title = f"%{t}%"
    return query.filter(
        (HarvestedCard.tickers.like(like_json))
        | (HarvestedCard.title.ilike(like_title))
    )


# ── endpoints ─────────────────────────────────────────────────────────────────

@app.get("/")
def root():
    return {
        "service": "nivesh-harvester",
        "status": "ok",
        "port": 8001,
        "endpoints": [
            "/harvester/feed",
            "/harvester/governance/{ticker}",
            "/harvester/sources",
            "/harvester/search",
            "/harvester/trigger/scrape",
            "/harvester/stats",
        ],
    }


@app.get("/harvester/feed")
def get_feed(
    ticker: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
):
    """Latest cards, newest first. Filtered by ticker when provided."""
    with get_session() as s:
        q = s.query(HarvestedCard)
        if ticker:
            q = _ticker_filter(q, ticker)
        rows = q.order_by(HarvestedCard.created_at.desc()).limit(limit).all()
        cards = [r.to_dict() for r in rows]
        sources = sorted({r.source_name for r in rows if r.source_name})
    return {"cards": cards, "total": len(cards), "sources": sources}


@app.get("/harvester/governance/{ticker}")
def get_governance(ticker: str, limit: int = Query(default=20, ge=1, le=100)):
    """GOVERNANCE cards for a specific ticker, newest first. Returns an array."""
    with get_session() as s:
        q = s.query(HarvestedCard).filter(HarvestedCard.card_type == "GOVERNANCE")
        q = _ticker_filter(q, ticker)
        rows = q.order_by(HarvestedCard.created_at.desc()).limit(limit).all()
        return [r.to_dict() for r in rows]


@app.get("/harvester/sources")
def get_sources():
    """Per-source health for the iOS 'Sources' sheet. Returns an array."""
    with get_session() as s:
        rows = s.query(SourceHealth).order_by(SourceHealth.source_name.asc()).all()
        return [r.to_dict() for r in rows]


@app.get("/harvester/search")
def search(q: str = Query(..., min_length=1), limit: int = Query(default=30, ge=1, le=100)):
    """Full-text search across titles and summaries."""
    needle = f"%{q.strip()}%"
    with get_session() as s:
        rows = (
            s.query(HarvestedCard)
            .filter(
                (HarvestedCard.title.ilike(needle))
                | (HarvestedCard.reformatted_summary.ilike(needle))
                | (HarvestedCard.raw_text.ilike(needle))
            )
            .order_by(HarvestedCard.created_at.desc())
            .limit(limit)
            .all()
        )
        cards = [r.to_dict() for r in rows]
    return {"query": q, "cards": cards, "total": len(cards)}


@app.post("/harvester/trigger/scrape")
def trigger_scrape(
    source: str = Query(..., pattern="^(sebi|expert|youtube)$"),
    limit: int = Query(default=20, ge=1, le=100),
):
    """Manually run one scrape job synchronously and return the counts."""
    try:
        result = run_scrape(source, limit=limit)
        return {"source": source, "ok": True, **result}
    except Exception as exc:  # noqa: BLE001
        logger.error("manual scrape failed: %s", exc)
        return {"source": source, "ok": False, "error": str(exc)}


@app.get("/harvester/stats")
def stats():
    """Aggregate counts: total, per source_type, per card_type, last runs."""
    with get_session() as s:
        total = s.query(HarvestedCard).count()

        by_source: dict[str, int] = {}
        for st, in s.query(HarvestedCard.source_type).all():
            by_source[st] = by_source.get(st, 0) + 1

        by_card_type: dict[str, int] = {}
        for ct, in s.query(HarvestedCard.card_type).all():
            by_card_type[ct] = by_card_type.get(ct, 0) + 1

        last_runs = {
            r.source_name: (r.last_success.isoformat() if r.last_success else None)
            for r in s.query(SourceHealth).all()
        }

    return {
        "total_cards": total,
        "by_source_type": by_source,
        "by_card_type": by_card_type,
        "last_run_times": last_runs,
    }
