"""
Nivesh Harvester — APScheduler jobs + the single reformatting pass.

Three periodic jobs (each isolated — one failing source never blocks another):
  sebi_harvest     — every 15 min
  expert_harvest   — every 60 min
  youtube_harvest  — every 120 min

Each job: scrape → store raw cards → run the DeepSeek reformatting pass over any
cards that are not yet reformatted. Rejected cards (credibility < 5) are deleted.

Also seeds the SourceHealth roster on startup so /harvester/sources always lists
the full set of sources, even before the first scrape completes.
"""

from __future__ import annotations

import json
import logging

from apscheduler.schedulers.background import BackgroundScheduler

from models import (
    HarvestedCard,
    SourceHealth,
    get_session,
    record_source_health,
    upsert_card,
)
from reformatter import reformat_single
from harvesters import (
    harvest_sebi_filings,
    scrape_all_expert_sources,
    harvest_youtube_transcripts,
)

logger = logging.getLogger("harvester.scheduler")

_scheduler: BackgroundScheduler | None = None

# Full roster shown by /harvester/sources from the very first boot.
SOURCE_ROSTER = [
    "NSE Corporate Announcements",
    "CRISIL Ratings",
    "ICRA Ratings",
    "CARE Ratings",
    "India Ratings & Research",
    "CNBC-TV18 Expert View",
    "Moneycontrol Expert Columns",
    "SEBI RIA Registry",
    "AMFI Mutual Fund Data",
    "YouTube Finance Channels",
]


def seed_source_health() -> None:
    """Insert a SourceHealth row for each known source if not already present.

    Returns:
        None
    """
    try:
        with get_session() as s:
            existing = {r.source_name for r in s.query(SourceHealth.source_name).all()}
            for name in SOURCE_ROSTER:
                if name not in existing:
                    s.add(SourceHealth(source_name=name, items_scraped=0, is_healthy=True))
    except Exception as exc:  # noqa: BLE001
        logger.error("seed_source_health failed: %s", exc)


# ═════════════════════════════════════════════════════════════════════════════
# The single reformatting pass
# ═════════════════════════════════════════════════════════════════════════════

def reformat_pending(limit: int = 40) -> int:
    """Reformat cards whose reformatted_summary is still NULL.

    Updates the card in place with the DeepSeek output, or DELETES it if the
    reformatter rejects it (credibility < 5). Returns the number reformatted.

    Args:
        limit (int, optional): Maximum number of cards to process. Defaults to 40.

    Returns:
        int: The number of cards successfully reformatted.
    """
    done = 0
    try:
        with get_session() as s:
            pending = (
                s.query(HarvestedCard)
                .filter(HarvestedCard.reformatted_summary.is_(None))
                .order_by(HarvestedCard.created_at.desc())
                .limit(max(1, limit))
                .all()
            )
            for card in pending:
                try:
                    result = reformat_single(
                        card.raw_text or card.title or "",
                        card.source_type,
                        card.source_name,
                        card.original_author,
                    )
                except Exception as exc:  # noqa: BLE001
                    logger.warning("reformat error for card %s: %s", card.id, exc)
                    continue

                if result is None:
                    # Rejected (credibility < 5) — never display it.
                    s.delete(card)
                    continue

                card.reformatted_summary = result.get("reformatted_summary") or card.raw_text[:400]
                card.key_takeaways = json.dumps(result.get("key_takeaways") or [], ensure_ascii=False)
                llm_tickers = result.get("tickers") or []
                if llm_tickers:
                    card.tickers = json.dumps(llm_tickers, ensure_ascii=False)
                card.sentiment = result.get("sentiment") or "NEUTRAL"
                if result.get("credibility_score"):
                    card.credibility_score = int(result["credibility_score"])
                if result.get("card_type"):
                    card.card_type = result["card_type"]
                if result.get("expert_credential"):
                    card.expert_credential = result["expert_credential"]
                if result.get("title"):
                    card.title = result["title"][:300]
                done += 1
        logger.info("[reformat] reformatted %d pending cards", done)
    except Exception as exc:  # noqa: BLE001
        logger.error("reformat_pending failed: %s", exc)
    return done


# ═════════════════════════════════════════════════════════════════════════════
# Jobs
# ═════════════════════════════════════════════════════════════════════════════

def run_sebi_job(limit: int = 30) -> dict:
    """Execute the SEBI filings harvest job.

    Args:
        limit (int, optional): Maximum number of filings to fetch. Defaults to 30.

    Returns:
        dict: A dictionary containing counts of stored and reformatted cards.
    """
    logger.info("[job:sebi] start")
    stored = harvest_sebi_filings(limit=limit)
    reformatted = reformat_pending(limit=max(stored, 10))
    logger.info("[job:sebi] stored=%d reformatted=%d", stored, reformatted)
    return {"stored": stored, "reformatted": reformatted}


def run_expert_job(limit: int = 30) -> dict:
    """Execute the expert sources harvest job.

    Args:
        limit (int, optional): Maximum number of items to process. Defaults to 30.

    Returns:
        dict: A dictionary containing counts of stored and reformatted cards.
    """
    logger.info("[job:expert] start")
    stored = 0
    seen: dict[str, int] = {}
    try:
        cards = scrape_all_expert_sources() or []
        with get_session() as s:
            for card in cards:
                name = card.get("source_name") or "Expert Source"
                if upsert_card(s, card):
                    stored += 1
                    seen[name] = seen.get(name, 0) + 1
            # mark every source that returned at least one item healthy
            for name, count in seen.items():
                record_source_health(s, name, success=True, items=count)
    except Exception as exc:  # noqa: BLE001
        logger.error("[job:expert] scrape/store failed: %s", exc)

    reformatted = reformat_pending(limit=max(stored, 20))
    logger.info("[job:expert] stored=%d reformatted=%d", stored, reformatted)
    return {"stored": stored, "reformatted": reformatted}


def run_youtube_job(limit: int = 20) -> dict:
    """Execute the YouTube finance channels harvest job.

    Args:
        limit (int, optional): Maximum number of videos to process. Defaults to 20.

    Returns:
        dict: A dictionary containing counts of stored and reformatted cards.
    """
    logger.info("[job:youtube] start")
    stored = harvest_youtube_transcripts(limit=limit)
    reformatted = reformat_pending(limit=max(stored, 10))
    logger.info("[job:youtube] stored=%d reformatted=%d", stored, reformatted)
    return {"stored": stored, "reformatted": reformatted}


def run_scrape(source: str, limit: int = 20) -> dict:
    """Synchronous manual trigger used by POST /harvester/trigger/scrape.

    Args:
        source (str): The identifier of the source to scrape ('sebi', 'expert', 'youtube').
        limit (int, optional): Maximum number of items to process. Defaults to 20.

    Returns:
        dict: Result dictionary from the respective job.

    Raises:
        ValueError: If an unknown source identifier is provided.
    """
    source = (source or "").lower().strip()
    if source == "sebi":
        return run_sebi_job(limit=limit)
    if source == "expert":
        return run_expert_job(limit=limit)
    if source == "youtube":
        return run_youtube_job(limit=limit)
    raise ValueError(f"unknown source '{source}' (use sebi|expert|youtube)")


# ═════════════════════════════════════════════════════════════════════════════
# Lifecycle
# ═════════════════════════════════════════════════════════════════════════════

def start_scheduler() -> None:
    """Initialize and start the background job scheduler.

    Returns:
        None
    """
    global _scheduler
    if _scheduler is not None:
        return

    seed_source_health()

    _scheduler = BackgroundScheduler(timezone="Asia/Kolkata")
    _scheduler.add_job(
        run_sebi_job, "interval", minutes=15, id="sebi_harvest",
        max_instances=1, coalesce=True,
    )
    _scheduler.add_job(
        run_expert_job, "interval", minutes=60, id="expert_harvest",
        max_instances=1, coalesce=True,
    )
    _scheduler.add_job(
        run_youtube_job, "interval", minutes=120, id="youtube_harvest",
        max_instances=1, coalesce=True,
    )
    _scheduler.start()
    logger.info("scheduler started (sebi/15m, expert/60m, youtube/120m)")

    # Kick an immediate first pass so the feed is populated shortly after boot.
    try:
        import threading

        threading.Thread(target=_initial_warmup, name="harvester-warmup", daemon=True).start()
    except Exception as exc:  # noqa: BLE001
        logger.warning("warmup thread failed to start: %s", exc)


def _initial_warmup() -> None:
    """Best-effort first scrape so /feed isn't empty right after startup.

    Returns:
        None
    """
    for fn in (run_expert_job, run_sebi_job):
        try:
            fn()
        except Exception as exc:  # noqa: BLE001
            logger.warning("warmup job failed: %s", exc)


def stop_scheduler() -> None:
    """Stop the background job scheduler gracefully.

    Returns:
        None
    """
    global _scheduler
    if _scheduler is not None:
        try:
            _scheduler.shutdown(wait=False)
        except Exception:
            pass
        _scheduler = None
        logger.info("scheduler stopped")
