"""
Harvester package — exports the three top-level harvest entry points.

Imports are defensive on purpose: if one harvester module fails to import
(e.g. an optional dependency like youtube-transcript-api is missing), the
others — and the FastAPI app as a whole — must still come up and serve 200.
A failed import is replaced with a no-op stub that records nothing.
"""

from __future__ import annotations

import logging

logger = logging.getLogger("harvester.init")

# ── SEBI / exchange filings ───────────────────────────────────────────────────
try:
    from .sebi_filings import harvest_sebi_filings  # noqa: F401
except Exception as exc:  # noqa: BLE001
    logger.error("sebi_filings import failed: %s", exc)

    def harvest_sebi_filings(limit: int = 30) -> int:  # type: ignore
        logger.error("harvest_sebi_filings unavailable (import failed)")
        return 0

# ── Expert sources (rating agencies, CNBC, Moneycontrol, SEBI RIA, AMFI) ──────
try:
    from .expert_scraper import scrape_all_expert_sources  # noqa: F401
except Exception as exc:  # noqa: BLE001
    logger.error("expert_scraper import failed: %s", exc)

    def scrape_all_expert_sources() -> list:  # type: ignore
        logger.error("scrape_all_expert_sources unavailable (import failed)")
        return []

# ── YouTube transcripts ───────────────────────────────────────────────────────
try:
    from .youtube_harvester import harvest_youtube_transcripts  # noqa: F401
except Exception as exc:  # noqa: BLE001
    logger.error("youtube_harvester import failed: %s", exc)

    def harvest_youtube_transcripts(limit: int = 20) -> int:  # type: ignore
        logger.error("harvest_youtube_transcripts unavailable (import failed)")
        return 0


__all__ = [
    "harvest_sebi_filings",
    "scrape_all_expert_sources",
    "harvest_youtube_transcripts",
]
