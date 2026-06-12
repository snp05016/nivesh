"""
SEBI / Exchange filings harvester.

Fetches the NSE corporate-announcements RSS feed through ScraperAPI
(residential-IP proxy), keeps only items that match governance red-flag
keywords (auditor/CFO/MD resignation, pledge invocation, SEBI orders,
insider trading, forensic audit, etc.), and stores them as raw GOVERNANCE
cards (credibility 10). The scheduler reformats them afterwards.

Fully defensive: if SCRAPERAPI_API_KEY is missing or the fetch fails,
it records a SourceHealth failure and returns 0. Never raises.

Public: harvest_sebi_filings(limit=30) -> int   (number of NEW cards stored)
"""

from __future__ import annotations

import logging
import os
import re

import feedparser
import requests

from services.harvester_db import get_session as h_get_session, upsert_card, record_source_health
from services.harvester_reformatter import make_external_id, derive_credential

logger = logging.getLogger("harvester.sebi")

NSE_RSS_URL = "https://www.nseindia.com/corporates/corpInfo/equities/rss/announcementsRss.xml"
SCRAPERAPI_URL = "http://api.scraperapi.com"
SOURCE_NAME = "NSE Corporate Announcements"

# Governance red-flag keywords (lower-cased match against title + summary).
GOVERNANCE_KEYWORDS = [
    "resignation of statutory auditor",
    "resignation of auditor",
    "auditor resignation",
    "resignation of managing director",
    "resignation of chief executive",
    "resignation of chief financial",
    "resignation of cfo",
    "pledge",
    "pledged shares",
    "invocation of pledge",
    "sebi order",
    "sebi action",
    "insider trading",
    "sast disclosure",
    "bulk deal",
    "block deal",
    "credit rating downgrade",
    "forensic audit",
    "related party transaction",
]

# Common all-caps words to drop when extracting tickers via regex.
_TICKER_STOPWORDS = {
    "THE", "AND", "FOR", "LTD", "LIMITED", "INDIA", "SEBI", "NSE", "BSE", "CEO",
    "CFO", "MD", "RSS", "XML", "INC", "PLC", "CO", "PVT", "AGM", "EGM", "IPO",
    "QIP", "NCD", "SAST", "RBI", "USD", "INR", "GST", "PAT", "EPS", "ROE",
    "ANNOUNCEMENT", "DISCLOSURE", "REGULATION", "REGULATIONS", "INTIMATION",
    "MEETING", "BOARD", "RESULTS", "OUTCOME", "TRADING", "WINDOW", "CLOSURE",
}
_TICKER_RE = re.compile(r"\b[A-Z][A-Z0-9&]{1,19}\b")


def _extract_tickers(text: str) -> list[str]:
    out: list[str] = []
    for tok in _TICKER_RE.findall(text or ""):
        if tok in _TICKER_STOPWORDS:
            continue
        if tok.isdigit():
            continue
        if tok not in out:
            out.append(tok)
    return out[:6]


def _build_scraperapi_url(target_url: str) -> str | None:
    """Build a ScraperAPI proxy URL.  Returns None when the key is missing."""
    key = os.environ.get("SCRAPERAPI_API_KEY", "").strip()
    if not key:
        logger.error("[sebi] SCRAPERAPI_API_KEY not set — cannot fetch NSE")
        return None
    return f"{SCRAPERAPI_URL}?api_key={key}&url={target_url}"


def _fetch_feed() -> list:
    """Fetch NSE RSS entries through ScraperAPI residential-IP proxy."""
    proxy_url = _build_scraperapi_url(NSE_RSS_URL)
    if not proxy_url:
        return []

    try:
        resp = requests.get(proxy_url, timeout=45)
        logger.info("[sebi] ScraperAPI RSS response: %s, content length: %s",
                     resp.status_code, len(resp.content or b""))
        if resp.status_code == 200 and resp.content and len(resp.content) > 100:
            parsed = feedparser.parse(resp.content)
            entries = getattr(parsed, "entries", []) or []
            logger.info("[sebi] RSS entries found: %d", len(entries))
            return entries
        logger.warning("[sebi] ScraperAPI returned status=%s len=%s",
                        resp.status_code, len(resp.content or b""))
    except Exception as exc:  # noqa: BLE001
        logger.warning("[sebi] ScraperAPI fetch failed: %s", exc)
    return []


def harvest_sebi_filings(limit: int = 30) -> int:
    """Scrape NSE filings, store governance-relevant ones. Never raises."""
    new_count = 0
    try:
        entries = _fetch_feed()
        if not entries:
            with h_get_session() as s:
                record_source_health(
                    s, SOURCE_NAME, success=False, error="no entries (feed blocked or empty)"
                )
            return 0

        with h_get_session() as s:
            for entry in entries[: max(1, limit)]:
                title = (getattr(entry, "title", "") or "").strip()
                summary = (getattr(entry, "summary", "") or getattr(entry, "description", "") or "").strip()
                link = (getattr(entry, "link", "") or "").strip()
                published = (
                    getattr(entry, "published", "")
                    or getattr(entry, "updated", "")
                    or ""
                )

                blob = f"{title} {summary}".lower()
                if not any(kw in blob for kw in GOVERNANCE_KEYWORDS):
                    continue  # only governance-relevant filings

                raw_text = f"{title}. {summary}".strip()
                card = {
                    "external_id": make_external_id(link, title),
                    "source_type": "SEBI_FILING",
                    "source_name": SOURCE_NAME,
                    "source_url": link,
                    "original_author": None,
                    "published_at": published or None,
                    "title": title[:300],
                    "raw_text": raw_text,
                    "tickers": _extract_tickers(f"{title} {summary}"),
                    "card_type": "GOVERNANCE",
                    "credibility_score": 10,
                    "expert_credential": derive_credential("SEBI_FILING"),
                }
                if upsert_card(s, card):
                    new_count += 1

            record_source_health(s, SOURCE_NAME, success=True, items=new_count)

        logger.info("[sebi] stored %d new governance cards", new_count)
        return new_count

    except Exception as exc:  # noqa: BLE001 — top-level guard, must never raise
        logger.error("[sebi] harvest failed: %s", exc)
        try:
            with h_get_session() as s:
                record_source_health(s, SOURCE_NAME, success=False, error=str(exc))
        except Exception:
            pass
        return 0
