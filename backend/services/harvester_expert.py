
"""
Nivesh Harvester — Expert & Credit-Rating sources scraper.

Collects three categories of expert/credentialed sources:
  1. Credit rating agency press releases (CRISIL, ICRA, CARE, India Ratings)
  2. SEBI RIA Registry reference card
  3. AMFI Mutual Fund NAV data reference card

Publisher columns (CNBC-TV18, Moneycontrol) are no longer scraped: their content
is copyrighted and needs a licensed or RSS source with reuse terms (REG-14). No
proxy services are used to get around site blocks.

Public API:
  scrape_all_expert_sources() -> list[dict]
    Returns combined raw card dicts, filtered to credibility_score >= 5.
    NEVER raises.

Each card dict keys: external_id, source_type, source_name, source_url,
original_author, published_at, title, raw_text, tickers, card_type,
credibility_score, expert_credential.
"""

from __future__ import annotations

import logging
from config.settings import get_user_agent
import re
from typing import Optional

import feedparser
import requests
from bs4 import BeautifulSoup

from services.harvester_reformatter import (
    derive_card_type,
    derive_credibility,
    derive_credential,
    make_external_id,
)

logger = logging.getLogger("harvester.expert")

# ── Request config ──────────────────────────────────────────────────────────
_BROWSER_HEADERS = {
    "User-Agent": get_user_agent(),
    "Accept": (
        "text/html,application/xhtml+xml,application/xml;q=0.9,"
        "image/avif,image/webp,*/*;q=0.8"
    ),
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
}
_TIMEOUT = 15

# ── Credit rating press-release pages ─────────────────────────────────────────
# RSS feeds discontinued by all Indian rating agencies (2024-2025).
# Press-release pages are JS-rendered SPAs with active bot detection.
# Strategy: plain HTTP fetch; if the page does not yield links, return 0 cards
# and let source health reflect the outage.
_RATING_FEEDS = [
    {
        "url": "https://www.crisil.com/en/home/newsroom/press-releases.html",
        "source_type": "CRISIL_RATING",
        "source_name": "CRISIL Ratings",
    },
    {
        "url": "https://www.icra.in/Research/ListViewPressRelease",
        "source_type": "ICRA_RATING",
        "source_name": "ICRA Ratings",
    },
    {
        "url": "https://www.careratings.com/press-release",
        "source_type": "CARE_RATING",
        "source_name": "CARE Ratings",
    },
    {
        "url": "https://www.indiaratings.co.in/PressReleases",
        "source_type": "INDIA_RATINGS",
        "source_name": "India Ratings & Research",
    },
]
_RATING_FEED_LIMIT = 8

# ── SEBI RIA & AMFI config ──────────────────────────────────────────────────
_SEBI_RIA_URL = (
    "https://www.sebi.gov.in/sebiweb/other/OtherAction.do"
    "?doRecognisedFpi=yes&intmId=13"
)
_AMFI_NAV_URL = "https://www.amfiindia.com/spages/NAVAll.txt"

# ── NSE ticker pattern (3-12 upper-case letters/digits, common suffixes) ───
_TICKER_RE = re.compile(
    r"\b([A-Z][A-Z0-9]{2,11}(?:-(?:BE|BL|EQ|N1|N2|SM|ST))?)\b"
)
# Words we never want to call a ticker even if they match the shape.
_TICKER_STOP_WORDS = frozenset(
    {
        "NSE", "BSE", "SEBI", "AMFI", "NSDL", "CDSL", "RBI", "SBI",
        "ICICI", "HDFC", "IDBI", "IFCI", "NABARD", "SIDBI",
        "FY", "Q1", "Q2", "Q3", "Q4", "H1", "H2",
        "INR", "GDP", "CPI", "WPI", "PLI", "EMI",
        "MNC", "IPO", "FPO", "OFS", "QIP", "NCD", "NCB",
        "CEO", "CFO", "CMD", "MD", "CTO", "COO",
        "PAT", "EBITDA", "EPS", "NAV", "NPA", "ROE", "ROA", "AUM",
        "FII", "DII", "MF", "PMS", "AIF",
        "CAGR", "IRR", "NPV", "DCF",
        "USA", "US", "UK", "EU", "UAE", "IMF", "WTO",
        "GOVT", "GOI", "MCA", "MOF", "RTO", "GST",
        "KYC", "AML", "PMLA",
        "THE", "FOR", "AND", "BUT", "NOT", "ARE", "HAS",
        "URL", "RSS", "PDF", "XML", "HTML", "API",
    }
)


# ═══════════════════════════════════════════════════════════════════════════
# Helper: text cleaning
# ═══════════════════════════════════════════════════════════════════════════

def _clean_text(html_or_text: str) -> str:
    """Strip HTML tags and collapse whitespace."""
    if not html_or_text:
        return ""
    soup = BeautifulSoup(html_or_text, "html.parser")
    text = soup.get_text(separator=" ")
    text = re.sub(r"\s+", " ", text).strip()
    return text


# ═══════════════════════════════════════════════════════════════════════════
# Helper: article content extraction
# ═══════════════════════════════════════════════════════════════════════════

def _extract_article_text(article_html: str) -> str:
    """Extract main article body text from HTML. Limit 6000 chars."""
    soup = BeautifulSoup(article_html, "html.parser")

    # Remove nav/footer/header/aside/script/style noise.
    for noise in soup.find_all(
        ["nav", "footer", "header", "aside", "script", "style", "noscript",
         "form", "iframe", "figure"]
    ):
        noise.decompose()

    # Try common article body selectors in preference order.
    candidates = [
        soup.find("article"),
        soup.find(class_=re.compile(r"article.body|articleBody|story.body|"
                                    r"content.body|post.content|entry.content",
                                    re.I)),
        soup.find(attrs={"itemprop": "articleBody"}),
        soup.find(id=re.compile(r"article|story|content|main", re.I)),
        soup.find("main"),
    ]
    for candidate in candidates:
        if candidate:
            text = candidate.get_text(separator=" ")
            text = re.sub(r"\s+", " ", text).strip()
            if len(text) > 200:
                return text[:6000]

    # Fallback: all paragraphs.
    paras = soup.find_all("p")
    text = " ".join(p.get_text(" ") for p in paras if len(p.get_text()) > 40)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:6000]


def _extract_title(article_html: str) -> str:
    """Extract page title from article HTML."""
    soup = BeautifulSoup(article_html, "html.parser")

    # Prefer OG title, then h1, then <title>.
    og = soup.find("meta", property="og:title")
    if og and og.get("content", "").strip():
        return og["content"].strip()[:300]

    h1 = soup.find("h1")
    if h1 and h1.get_text(strip=True):
        return h1.get_text(strip=True)[:300]

    title_tag = soup.find("title")
    if title_tag and title_tag.get_text(strip=True):
        return title_tag.get_text(strip=True)[:300]

    return ""


# ═══════════════════════════════════════════════════════════════════════════
# Helper: ticker detection
# ═══════════════════════════════════════════════════════════════════════════

def _detect_tickers(text: str) -> list[str]:
    """Heuristically extract NSE-style ticker symbols from free text."""
    found: list[str] = []
    for match in _TICKER_RE.finditer(text):
        sym = match.group(1).upper()
        if sym in _TICKER_STOP_WORDS:
            continue
        if sym not in found:
            found.append(sym)
    return found[:10]  # cap to avoid noise


# ═══════════════════════════════════════════════════════════════════════════
# Helper: safe fetch
# ═══════════════════════════════════════════════════════════════════════════

def _fetch(url: str) -> Optional[requests.Response]:
    """GET with browser headers and timeout. Returns None on any error."""
    try:
        resp = requests.get(url, headers=_BROWSER_HEADERS, timeout=_TIMEOUT)
        if resp.status_code == 200:
            return resp
        logger.warning("Non-200 (%d) fetching %s", resp.status_code, url)
        return None
    except Exception as exc:
        logger.warning("Fetch error for %s: %s", url, exc)
        return None


# ═══════════════════════════════════════════════════════════════════════════
# Helper: build a raw card dict
# ═══════════════════════════════════════════════════════════════════════════

def _make_card(
    *,
    source_type: str,
    source_name: str,
    source_url: str,
    title: str,
    raw_text: str,
    original_author: Optional[str] = None,
    published_at: Optional[str] = None,
    tickers: Optional[list[str]] = None,
) -> dict:
    """Assemble a raw card dict with all required keys."""
    if tickers is None:
        tickers = _detect_tickers(raw_text)
    ext_id = make_external_id(source_url, raw_text)
    return {
        "external_id": ext_id,
        "source_type": source_type,
        "source_name": source_name,
        "source_url": source_url,
        "original_author": original_author,
        "published_at": published_at,
        "title": title or raw_text[:120],
        "raw_text": raw_text[:6000],
        "tickers": tickers or [],
        "card_type": derive_card_type(source_type),
        "credibility_score": derive_credibility(source_type),
        "expert_credential": derive_credential(source_type),
    }


# ═══════════════════════════════════════════════════════════════════════════
# Source 1: Credit rating agency RSS feeds
# ═══════════════════════════════════════════════════════════════════════════

def _scrape_rating_feed(feed_cfg: dict) -> list[dict]:
    """Scrape one credit-rating press-release page and return raw cards.

    Direct HTTP only; on failure return no cards (source health shows the outage).
    """
    url = feed_cfg["url"]
    source_type = feed_cfg["source_type"]
    source_name = feed_cfg["source_name"]
    cards: list[dict] = []

    try:
        resp = _fetch(url)
        if resp is None:
            logger.warning("Rating source %s: all fetch methods failed", source_name)
            return cards

        # Parse rendered HTML for article/press-release links
        soup = BeautifulSoup(resp.text, "html.parser")
        raw_links: list[str] = []
        for a in soup.find_all("a", href=True):
            href = a["href"].strip()
            if not href or href.startswith("#") or href.startswith("javascript"):
                continue
            # Accept any same-domain link with 2+ path segments
            from urllib.parse import urljoin, urlparse
            full = urljoin(url, href)
            parsed = urlparse(full)
            path_segs = [p for p in parsed.path.split("/") if p]
            if len(path_segs) >= 2 and parsed.scheme in ("http", "https"):
                clean = full.split("?")[0].rstrip("/")
                if clean not in raw_links:
                    raw_links.append(clean)

        # If no article links found in rendered HTML, try feedparser as last resort
        if not raw_links:
            logger.warning("Rating source %s: 0 article links in rendered HTML", source_name)
            return cards

        # Fetch each linked press release and extract content
        for article_url in raw_links[:_RATING_FEED_LIMIT]:
            try:
                art_resp = _fetch(article_url)
                if art_resp is None:
                    continue
                title = _extract_title(art_resp.text)
                body = _extract_article_text(art_resp.text)
                if not body or len(body) < 100:
                    continue

                cards.append(
                    _make_card(
                        source_type=source_type,
                        source_name=source_name,
                        source_url=article_url,
                        title=title,
                        raw_text=body,
                        original_author=None,
                    )
                )
            except Exception as exc:
                logger.warning("Rating article %s failed: %s", article_url, exc)

    except Exception as exc:
        logger.warning("Rating source %s failed: %s", source_name, exc)

    logger.info("Rating source %s: %d cards", source_name, len(cards))
    return cards


def _scrape_all_rating_agencies() -> list[dict]:
    """Scrape all four credit-rating RSS feeds."""
    cards: list[dict] = []
    for feed_cfg in _RATING_FEEDS:
        try:
            cards.extend(_scrape_rating_feed(feed_cfg))
        except Exception as exc:
            logger.warning("Unexpected error for rating agency %s: %s",
                           feed_cfg["source_name"], exc)
    return cards


# ═══════════════════════════════════════════════════════════════════════════
# Source 2: SEBI RIA Registry (reference card)
# ═══════════════════════════════════════════════════════════════════════════

def _scrape_sebi_ria_registry() -> list[dict]:
    """
    Emit ONE reference card about the SEBI Registered Investment Advisor
    registry, built from the fetched page. No card when the fetch fails
    (SILENT-18: no boilerplate posing as harvested content).
    """
    source_type = "SEBI_RIA_NOTE"
    source_name = "SEBI RIA Registry"
    source_url = _SEBI_RIA_URL

    page_snippet = ""
    try:
        resp = _fetch(_SEBI_RIA_URL)
        if resp is not None:
            page_text = _clean_text(resp.text)
            # Grab first meaningful chunk of the page.
            page_snippet = page_text[:1000].strip()
    except Exception as exc:
        logger.warning("SEBI RIA registry fetch failed: %s", exc)

    if not page_snippet:
        logger.warning("SEBI RIA Registry: fetch failed or empty, no card")
        return []
    raw_text = (
        "SEBI Registered Investment Advisor (RIA) Registry — "
        "official registry of SEBI-licensed, fiduciary-duty investment advisors "
        "who are legally accountable for advice given to retail investors. "
        f"Page content excerpt: {page_snippet}"
    )

    card = _make_card(
        source_type=source_type,
        source_name=source_name,
        source_url=source_url,
        title="SEBI Registered Investment Advisor Registry",
        raw_text=raw_text,
        tickers=[],
    )
    logger.info("SEBI RIA Registry: 1 card")
    return [card]


# ═══════════════════════════════════════════════════════════════════════════
# Source 3: AMFI Mutual Fund Data (reference card)
# ═══════════════════════════════════════════════════════════════════════════

def _scrape_amfi_nav_data() -> list[dict]:
    """
    Emit ONE reference card summarising the fetched AMFI NAV data.
    No card when the fetch fails (SILENT-18).
    """
    source_type = "AMFI_DATA"
    source_name = "AMFI Mutual Fund Data"
    source_url = _AMFI_NAV_URL

    summary_detail = ""
    try:
        resp = _fetch(_AMFI_NAV_URL)
        if resp is not None:
            lines = [l.strip() for l in resp.text.splitlines() if l.strip()]
            scheme_count = sum(1 for l in lines if ";" in l)  # data lines have semicolons
            header_lines = [l for l in lines if ";" not in l and l]
            first_header = header_lines[0] if header_lines else ""
            summary_detail = (
                f"NAVAll.txt parsed: {len(lines)} total lines, "
                f"approximately {scheme_count} scheme NAV entries. "
            )
            if first_header:
                summary_detail += f"First header line: {first_header[:200]}."
    except Exception as exc:
        logger.warning("AMFI NAV fetch failed: %s", exc)

    if not summary_detail:
        logger.warning("AMFI MF Data: fetch failed or empty, no card")
        return []
    raw_text = (
        "AMFI (Association of Mutual Funds in India) publishes daily mutual-fund "
        "NAV data for all schemes registered in India. This is a key macro data "
        "source for tracking AUM flows, redemptions, and fund-manager positioning "
        "across equity, debt, and hybrid categories. "
        + summary_detail
    )

    card = _make_card(
        source_type=source_type,
        source_name=source_name,
        source_url=source_url,
        title="AMFI India — Mutual Fund NAV & AUM Data",
        raw_text=raw_text,
        tickers=[],
    )
    logger.info("AMFI MF Data: 1 card")
    return [card]


# ═══════════════════════════════════════════════════════════════════════════
# Public API
# ═══════════════════════════════════════════════════════════════════════════

_MIN_CREDIBILITY = 5
_SEBI_SOURCE_NAME = "SEBI RIA Registry"
_AMFI_SOURCE_NAME = "AMFI Mutual Fund Data"
_RATING_SOURCE_NAMES = [f["source_name"] for f in _RATING_FEEDS]
# Every source_name this module produces; each gets a SourceHealth outcome per run.
_EXPECTED_SOURCES = [*_RATING_SOURCE_NAMES, _SEBI_SOURCE_NAME, _AMFI_SOURCE_NAME]


def _record_expert_health(all_cards: list[dict], errors: dict[str, str]) -> None:
    """SILENT-18: record a real outcome for every expected source (0 cards = failure)."""
    try:
        from services.harvester_db import get_session as h_get_session, record_source_health
        with h_get_session() as s:
            for name in _EXPECTED_SOURCES:
                count = sum(1 for c in all_cards if c.get("source_name") == name)
                record_source_health(
                    s, name, success=count > 0, items=count,
                    error=None if count else errors.get(name, "no items harvested (fetch failed or empty)"),
                )
    except Exception:
        logger.warning("Recording expert source health failed", exc_info=True)


def scrape_all_expert_sources() -> list[dict]:
    """Run all expert sources, return combined RAW card dicts.

    Filters out anything with credibility_score < 5. NEVER raises.
    """
    all_cards: list[dict] = []

    errors: dict[str, str] = {}

    sources = [
        ("credit_rating_agencies", _scrape_all_rating_agencies, _RATING_SOURCE_NAMES),
        ("sebi_ria_registry", _scrape_sebi_ria_registry, [_SEBI_SOURCE_NAME]),
        ("amfi_nav_data", _scrape_amfi_nav_data, [_AMFI_SOURCE_NAME]),
    ]

    for name, scrape_fn, source_names in sources:
        try:
            cards = scrape_fn()
            all_cards.extend(cards)
        except Exception as exc:
            logger.warning("Source '%s' raised unexpectedly: %s", name, exc)
            errors.update({sn: str(exc)[:500] or type(exc).__name__ for sn in source_names})
            try:
                from services.error_telemetry import log_diagnostic_error
                log_diagnostic_error(
                    subsystem="HARVESTER_EXPERT",
                    classification="HARVEST_FAILURE",
                    context={"source_name": name},
                    exception={"type": type(exc).__name__, "message": str(exc)},
                )
            except Exception:
                logger.warning("Harvest failure telemetry write failed", exc_info=True)

    _record_expert_health(all_cards, errors)

    # Final credibility filter.
    filtered = [c for c in all_cards if c.get("credibility_score", 0) >= _MIN_CREDIBILITY]
    dropped = len(all_cards) - len(filtered)
    if dropped:
        logger.info("Dropped %d cards with credibility_score < %d", dropped, _MIN_CREDIBILITY)

    logger.info(
        "scrape_all_expert_sources complete: %d cards returned (%d total before filter)",
        len(filtered), len(all_cards),
    )
    return filtered
