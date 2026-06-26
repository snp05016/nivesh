"""
Harvester endpoints — ported from nivesh-harvester/main.py into the main backend.

All data endpoints require auth. /sources is public (health check).
Admin endpoints (trigger/stats) require admin auth.

Endpoints:
  GET  /harvester/feed?ticker=&limit=         — auth required
  GET  /harvester/governance/{ticker}         — auth required
  GET  /harvester/sources                     — PUBLIC (no auth)
  GET  /harvester/search?q=                   — auth required
  POST /harvester/trigger/scrape?source=&limit= — ADMIN only
  GET  /harvester/stats                       — ADMIN only
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Query, Header, HTTPException

from services.harvester_db import get_session as h_get_session, HarvestedCard, SourceHealth
from services.harvester_sebi import harvest_sebi_filings
from services.harvester_expert import scrape_all_expert_sources
from services.expert_youtube_harvester import harvest_youtube_transcripts
from services.harvester_reformatter import reformat_single, make_external_id
from helpers import require_auth, require_admin

logger = logging.getLogger("harvester.router")

router = APIRouter(prefix="/harvester", tags=["harvester"])


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


def reformat_pending(limit: int = 50) -> int:
    """Reformat cards that have no reformatted_summary yet. Returns count updated."""
    updated = 0
    with h_get_session() as s:
        rows = (
            s.query(HarvestedCard)
            .filter(HarvestedCard.reformatted_summary == None)  # noqa: E711
            .limit(limit)
            .all()
        )
        for row in rows:
            try:
                result = reformat_single(
                    raw_text=row.raw_text or "",
                    source_type=row.source_type or "EXPERT",
                    source_name=row.source_name or "",
                    original_author=row.original_author,
                )
                if result:
                    import json
                    row.reformatted_summary = result.get("reformatted_summary")
                    kts = result.get("key_takeaways", [])
                    row.key_takeaways = json.dumps(kts, ensure_ascii=False) if kts else None
                    tks = result.get("tickers", [])
                    if tks:
                        row.tickers = json.dumps(tks, ensure_ascii=False)
                    row.sentiment = result.get("sentiment")
                    row.credibility_score = result.get("credibility_score", row.credibility_score)
                    row.expert_credential = result.get("expert_credential") or row.expert_credential
                    updated += 1
            except Exception as exc:
                logger.warning("reformat_pending: failed for card id=%s: %s", row.id, exc)
    return updated


# ── endpoints ─────────────────────────────────────────────────────────────────

@router.get("/feed")
def get_feed(
    ticker: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    authorization: str = Header(None),
):
    """
    Latest cards, newest first. Filtered by ticker when provided. Auth required.

    Args:
        ticker (Any): The ticker.
        limit (int): The limit.
        authorization (str): The authorization.

    Returns:
        Any: The response.
    """
    require_auth(authorization)
    with h_get_session() as s:
        q = s.query(HarvestedCard)
        if ticker:
            q = _ticker_filter(q, ticker)
        rows = q.order_by(HarvestedCard.created_at.desc()).limit(limit).all()
        cards = [r.to_dict() for r in rows]
        sources = sorted({r.source_name for r in rows if r.source_name})
    return {"cards": cards, "total": len(cards), "sources": sources}


@router.get("/governance/{ticker}")
def get_governance(ticker: str, limit: int = Query(default=20, ge=1, le=100), authorization: str = Header(None)):
    """
    GOVERNANCE cards for a specific ticker, newest first. Auth required.

    Args:
        ticker (str): The ticker.
        limit (int): The limit.
        authorization (str): The authorization.

    Returns:
        Any: The response.
    """
    require_auth(authorization)
    with h_get_session() as s:
        q = s.query(HarvestedCard).filter(HarvestedCard.card_type == "GOVERNANCE")
        q = _ticker_filter(q, ticker)
        rows = q.order_by(HarvestedCard.created_at.desc()).limit(limit).all()
        return [r.to_dict() for r in rows]


@router.get("/sources")
def get_sources():
    """
    Per-source health for the iOS 'Sources' sheet. Returns an array.

    Args:

    Returns:
        Any: The response.
    """
    with h_get_session() as s:
        rows = s.query(SourceHealth).order_by(SourceHealth.source_name.asc()).all()
        return [r.to_dict() for r in rows]


@router.get("/search")
def search(q: str = Query(..., min_length=1), limit: int = Query(default=30, ge=1, le=100), authorization: str = Header(None)):
    """
    Full-text search across titles and summaries. Auth required.

    Args:
        q (str): The q.
        limit (int): The limit.
        authorization (str): The authorization.

    Returns:
        Any: The response.
    """
    require_auth(authorization)
    needle = f"%{q.strip()}%"
    with h_get_session() as s:
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


@router.post("/trigger/scrape")
def trigger_scrape(
    source: str = Query(..., pattern="^(sebi|expert|youtube)$"),
    limit: int = Query(default=20, ge=1, le=100),
    authorization: str = Header(None),
):
    """
    Manually run one scrape job synchronously. Admin only.

    Args:
        source (str): The source.
        limit (int): The limit.
        authorization (str): The authorization.

    Returns:
        Any: The response.
    """
    require_admin(authorization)
    try:
        if source == "sebi":
            new_cards = harvest_sebi_filings(limit=limit)
            result = {"new_cards": new_cards}
        elif source == "expert":
            cards = scrape_all_expert_sources()
            from services.harvester_db import upsert_card
            count = 0
            for card in cards[:limit]:
                with h_get_session() as s:
                    if upsert_card(s, card):
                        count += 1
            result = {"new_cards": count, "scraped": len(cards)}
        elif source == "youtube":
            new_cards = harvest_youtube_transcripts(limit=limit)
            result = {"new_cards": new_cards}
        else:
            result = {"error": "unknown source"}
        return {"source": source, "ok": True, **result}
    except Exception as exc:  # noqa: BLE001
        logger.error("manual scrape failed: %s", exc)
        return {"source": source, "ok": False, "error": str(exc)}


@router.get("/stats")
def stats(authorization: str = Header(None)):
    """
    Aggregate counts: total, per source_type, per card_type, last runs. Admin only.

    Args:
        authorization (str): The authorization.

    Returns:
        Any: The response.
    """
    require_admin(authorization)
    with h_get_session() as s:
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
