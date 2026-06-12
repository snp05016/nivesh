"""
SEBI / Exchange filings harvester.

Scrapes the NSE corporate-announcements RSS feed, keeps only items that match
governance red-flag keywords (auditor/CFO/MD resignation, pledge invocation,
SEBI orders, insider trading, forensic audit, etc.), and stores them as raw
GOVERNANCE cards (credibility 10). The scheduler reformats them afterwards.

Fully defensive: NSE blocks many datacenter IPs, so a failed fetch must NOT
raise — it records a SourceHealth failure and returns 0.

Public: harvest_sebi_filings(limit=30) -> int   (number of NEW cards stored)
"""

from __future__ import annotations

import logging
import re

import feedparser
import requests

from models import get_session, upsert_card, record_source_health
from reformatter import make_external_id, derive_credential

logger = logging.getLogger("harvester.sebi")

NSE_RSS_URL = "https://www.nseindia.com/corporates/corpInfo/equities/rss/announcementsRss.xml"
SOURCE_NAME = "NSE Corporate Announcements"

_BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    ),
    "Accept": "application/rss+xml, application/xml, text/xml, */*",
    "Accept-Language": "en-US,en;q=0.9",
}

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


def _fetch_feed() -> list:
    """Return RSS entries. Tries direct parse, then a browser-headed fetch."""
    try:
        parsed = feedparser.parse(NSE_RSS_URL, request_headers=_BROWSER_HEADERS)
        if getattr(parsed, "entries", None):
            return parsed.entries
    except Exception as exc:  # noqa: BLE001
        logger.warning("feedparser direct fetch failed: %s", exc)

    try:
        resp = requests.get(NSE_RSS_URL, headers=_BROWSER_HEADERS, timeout=15)
        if resp.status_code == 200 and resp.content:
            parsed = feedparser.parse(resp.content)
            return getattr(parsed, "entries", []) or []
        logger.warning("NSE RSS HTTP %s", resp.status_code)
    except Exception as exc:  # noqa: BLE001
        logger.warning("NSE RSS requests fetch failed: %s", exc)
    return []


def harvest_sebi_filings(limit: int = 30) -> int:
    """Scrape NSE filings, store governance-relevant ones. Never raises."""
    new_count = 0
    try:
        entries = _fetch_feed()
        if not entries:
            with get_session() as s:
                record_source_health(
                    s, SOURCE_NAME, success=False, error="no entries (feed blocked or empty)"
                )
            return 0

        with get_session() as s:
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
            with get_session() as s:
                record_source_health(s, SOURCE_NAME, success=False, error=str(exc))
        except Exception:
            pass
        return 0
