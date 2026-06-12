"""
Nivesh Harvester — Expert & Credit-Rating sources scraper.

Scrapes five categories of expert/credentialed sources:
  1. Credit rating agency RSS feeds (CRISIL, ICRA, CARE, India Ratings)
  2. CNBC-TV18 expert interview pages
  3. Moneycontrol expert columns (named authors only)
  4. SEBI RIA Registry reference card
  5. AMFI Mutual Fund NAV data reference card

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
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": (
        "text/html,application/xhtml+xml,application/xml;q=0.9,"
        "image/avif,image/webp,*/*;q=0.8"
    ),
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
}
_TIMEOUT = 15

# ── Credit rating RSS feed definitions ─────────────────────────────────────
_RATING_FEEDS = [
    {
        "url": "https://www.crisil.com/en/home/newsroom/rss/rating-actions.html",
        "source_type": "CRISIL_RATING",
        "source_name": "CRISIL Ratings",
    },
    {
        "url": "https://www.icra.in/RSS/RSSFeeds.aspx?feed=pressreleases",
        "source_type": "ICRA_RATING",
        "source_name": "ICRA Ratings",
    },
    {
        "url": "https://www.careratings.com/rss/press-release",
        "source_type": "CARE_RATING",
        "source_name": "CARE Ratings",
    },
    {
        "url": "https://www.indiaratings.co.in/rss/pressreleases",
        "source_type": "INDIA_RATINGS",
        "source_name": "India Ratings & Research",
    },
]
_RATING_FEED_LIMIT = 15

# ── CNBC-TV18 listing pages ─────────────────────────────────────────────────
_CNBC_LISTING_URLS = [
    "https://www.cnbctv18.com/market/expert-view/",
    "https://www.cnbctv18.com/market/stocks/",
    "https://www.cnbctv18.com/business/market/",
]
_CNBC_SOURCE_TYPE = "FUND_MANAGER_INTERVIEW"
_CNBC_SOURCE_NAME = "CNBC-TV18 Expert View"
_CNBC_ARTICLE_LIMIT = 6

# ── Moneycontrol listing pages ──────────────────────────────────────────────
_MC_LISTING_URLS = [
    "https://www.moneycontrol.com/news/business/stocks/",
    "https://www.moneycontrol.com/news/opinion/",
    "https://www.moneycontrol.com/news/business/markets/",
]
_MC_SOURCE_TYPE = "EXPERT_COLUMN"
_MC_SOURCE_NAME = "Moneycontrol Expert Columns"
_MC_ARTICLE_LIMIT = 6

# Wire-service by-lines to skip (case-insensitive exact match after strip).
_WIRE_SERVICE_AUTHORS = frozenset(
    {
        "moneycontrol",
        "reuters",
        "pti",
        "ians",
        "bloombergquint desk",
        "fpj web desk",
        "et online",
        "moneycontrol news",
        "moneycontrol desk",
        "mc news desk",
    }
)

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
# Helper: article discovery
# ═══════════════════════════════════════════════════════════════════════════

def _extract_article_links(listing_html: str, base_url: str) -> list[str]:
    """Return absolute article hrefs from a listing page HTML."""
    soup = BeautifulSoup(listing_html, "html.parser")
    from urllib.parse import urljoin, urlparse

    seen: set[str] = set()
    links: list[str] = []

    parsed_base = urlparse(base_url)
    base_domain = parsed_base.netloc  # e.g. "www.cnbctv18.com"

    for tag in soup.find_all("a", href=True):
        href: str = tag["href"].strip()
        if not href or href.startswith("#") or href.startswith("javascript"):
            continue
        full = urljoin(base_url, href)
        parsed = urlparse(full)

        # Keep only same-domain, http(s) links that look like article paths.
        if parsed.netloc != base_domain:
            continue
        if parsed.scheme not in ("http", "https"):
            continue
        # Heuristic: paths with at least 2 segments and NOT just a category root.
        path_parts = [p for p in parsed.path.split("/") if p]
        if len(path_parts) < 2:
            continue
        # Exclude pagination/tag/search/author archive pages.
        if any(
            seg in ("tag", "author", "search", "page", "category", "feed", "rss")
            for seg in path_parts
        ):
            continue
        clean = full.split("?")[0].rstrip("/")
        if clean not in seen:
            seen.add(clean)
            links.append(clean)

    return links


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


def _extract_article_author(article_html: str) -> Optional[str]:
    """Extract byline author name from article HTML. Returns None if not found."""
    soup = BeautifulSoup(article_html, "html.parser")

    # 1. JSON-LD structured data.
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            import json
            data = json.loads(script.string or "")
            # May be a single dict or a list.
            items = data if isinstance(data, list) else [data]
            for item in items:
                author = item.get("author")
                if isinstance(author, dict):
                    name = author.get("name", "").strip()
                    if name:
                        return name
                elif isinstance(author, list) and author:
                    name = (author[0] or {}).get("name", "").strip()
                    if name:
                        return name
        except Exception:
            pass

    # 2. Common meta / schema attributes.
    for selector, attr in [
        ({"name": "author"}, "content"),
        ({"property": "article:author"}, "content"),
        ({"itemprop": "author"}, "content"),
    ]:
        tag = soup.find("meta", selector)
        if tag and tag.get(attr, "").strip():
            return tag[attr].strip()

    # 3. CSS class / itemprop heuristics.
    for pattern in [
        re.compile(r"author|byline|writer", re.I),
    ]:
        for tag in soup.find_all(attrs={"class": pattern}):
            text = tag.get_text(strip=True)
            if text and 3 < len(text) < 80:
                # Strip common prefixes.
                text = re.sub(r"^(?:by|author|written by)[:\s]*", "", text, flags=re.I).strip()
                if text:
                    return text

        for tag in soup.find_all(attrs={"itemprop": pattern}):
            text = tag.get_text(strip=True)
            if text and 3 < len(text) < 80:
                return text

    return None


# ═══════════════════════════════════════════════════════════════════════════
# Helper: expert quote extraction
# ═══════════════════════════════════════════════════════════════════════════

# Pattern: "First Last, [Title] at/of [Org], said/says/believes/expects/notes"
_EXPERT_QUOTE_RE = re.compile(
    r"([A-Z][a-z]+(?: [A-Z][a-z]+)+)"         # Name (two+ capitalised words)
    r",\s*"
    r"([^,]{5,80})"                             # Title/role
    r"(?:\s+(?:at|of|with|from)\s+[^,]{3,60})?"  # optional "at Org"
    r",?\s*"
    r"(?:said|says|told|believes|expects|noted|notes|added|highlighted|"
    r"explained|pointed out|mentioned|stated|emphasised|emphasized)",
    re.IGNORECASE,
)


def _extract_expert_quotes(text: str) -> list[str]:
    """Return list of excerpt strings that contain an attributable expert quote."""
    quotes: list[str] = []
    for match in _EXPERT_QUOTE_RE.finditer(text):
        start = max(0, match.start() - 50)
        end = min(len(text), match.end() + 300)
        snippet = text[start:end].strip()
        if snippet:
            quotes.append(snippet)
    return quotes


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
    """Parse one credit-rating RSS feed and return raw cards."""
    url = feed_cfg["url"]
    source_type = feed_cfg["source_type"]
    source_name = feed_cfg["source_name"]
    cards: list[dict] = []

    try:
        resp = _fetch(url)
        if resp is None:
            # feedparser can also parse directly (tries its own request).
            parsed = feedparser.parse(url)
        else:
            parsed = feedparser.parse(resp.text)

        entries = parsed.get("entries", [])[:_RATING_FEED_LIMIT]
        if not entries:
            logger.warning("No entries in rating feed: %s", url)

        for entry in entries:
            try:
                title = _clean_text(entry.get("title", ""))
                summary = _clean_text(
                    entry.get("summary", "")
                    or entry.get("description", "")
                    or entry.get("content", [{}])[0].get("value", "")
                )
                raw_text = f"{title}. {summary}".strip() if summary else title
                if not raw_text:
                    continue

                link = entry.get("link", url)
                published = entry.get("published", None) or entry.get("updated", None)

                cards.append(
                    _make_card(
                        source_type=source_type,
                        source_name=source_name,
                        source_url=link,
                        title=title,
                        raw_text=raw_text,
                        published_at=published,
                        original_author=None,
                    )
                )
            except Exception as exc:
                logger.warning("Error parsing rating entry from %s: %s", url, exc)

    except Exception as exc:
        logger.warning("Rating feed %s failed: %s", url, exc)

    logger.info("Rating feed %s: %d cards", source_name, len(cards))
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
# Source 2: CNBC-TV18 Expert Interviews
# ═══════════════════════════════════════════════════════════════════════════

def _scrape_cnbc_expert_views() -> list[dict]:
    """Scrape CNBC-TV18 expert-view articles. Returns raw cards."""
    cards: list[dict] = []
    seen_urls: set[str] = set()

    for listing_url in _CNBC_LISTING_URLS:
        if len(cards) >= _CNBC_ARTICLE_LIMIT:
            break
        try:
            resp = _fetch(listing_url)
            if resp is None:
                continue
            links = _extract_article_links(resp.text, listing_url)
            for article_url in links:
                if len(cards) >= _CNBC_ARTICLE_LIMIT:
                    break
                if article_url in seen_urls:
                    continue
                seen_urls.add(article_url)
                try:
                    art_resp = _fetch(article_url)
                    if art_resp is None:
                        continue
                    title = _extract_title(art_resp.text)
                    body = _extract_article_text(art_resp.text)
                    if not body:
                        continue

                    # Only keep articles with a detectable expert attribution.
                    quotes = _extract_expert_quotes(body)
                    if not quotes:
                        continue

                    # Extract author from attribution in the quotes if possible.
                    author = _extract_article_author(art_resp.text)
                    # Derive a better credential from the first matched name+title.
                    expert_credential = derive_credential(_CNBC_SOURCE_TYPE)
                    match = _EXPERT_QUOTE_RE.search(body)
                    if match:
                        expert_name = match.group(1).strip()
                        expert_role = match.group(2).strip()
                        expert_credential = f"{expert_name}, {expert_role}"
                        if not author:
                            author = expert_name

                    card = _make_card(
                        source_type=_CNBC_SOURCE_TYPE,
                        source_name=_CNBC_SOURCE_NAME,
                        source_url=article_url,
                        title=title,
                        raw_text=body,
                        original_author=author,
                    )
                    # Override expert_credential with inline attribution if found.
                    card["expert_credential"] = expert_credential
                    cards.append(card)
                except Exception as exc:
                    logger.warning("CNBC article %s failed: %s", article_url, exc)
        except Exception as exc:
            logger.warning("CNBC listing %s failed: %s", listing_url, exc)

    logger.info("CNBC-TV18: %d cards", len(cards))
    return cards


# ═══════════════════════════════════════════════════════════════════════════
# Source 3: Moneycontrol Expert Columns
# ═══════════════════════════════════════════════════════════════════════════

def _is_wire_service_author(author: Optional[str]) -> bool:
    """Return True if author matches a known wire-service byline to skip."""
    if not author:
        return True  # No named author → treat as wire/anonymous → skip.
    return author.strip().lower() in _WIRE_SERVICE_AUTHORS


def _scrape_moneycontrol_expert_columns() -> list[dict]:
    """Scrape Moneycontrol expert columns, skipping wire-service reposts."""
    cards: list[dict] = []
    seen_urls: set[str] = set()

    for listing_url in _MC_LISTING_URLS:
        if len(cards) >= _MC_ARTICLE_LIMIT:
            break
        try:
            resp = _fetch(listing_url)
            if resp is None:
                continue
            links = _extract_article_links(resp.text, listing_url)
            for article_url in links:
                if len(cards) >= _MC_ARTICLE_LIMIT:
                    break
                if article_url in seen_urls:
                    continue
                seen_urls.add(article_url)
                try:
                    art_resp = _fetch(article_url)
                    if art_resp is None:
                        continue
                    author = _extract_article_author(art_resp.text)
                    if _is_wire_service_author(author):
                        continue  # Wire-service repost — skip.
                    title = _extract_title(art_resp.text)
                    body = _extract_article_text(art_resp.text)
                    if not body:
                        continue

                    cards.append(
                        _make_card(
                            source_type=_MC_SOURCE_TYPE,
                            source_name=_MC_SOURCE_NAME,
                            source_url=article_url,
                            title=title,
                            raw_text=body,
                            original_author=author,
                        )
                    )
                except Exception as exc:
                    logger.warning("MC article %s failed: %s", article_url, exc)
        except Exception as exc:
            logger.warning("MC listing %s failed: %s", listing_url, exc)

    logger.info("Moneycontrol Expert Columns: %d cards", len(cards))
    return cards


# ═══════════════════════════════════════════════════════════════════════════
# Source 4: SEBI RIA Registry (reference card)
# ═══════════════════════════════════════════════════════════════════════════

def _scrape_sebi_ria_registry() -> list[dict]:
    """
    Emit ONE reference card about the SEBI Registered Investment Advisor
    registry. Even if the page fetch fails we still emit the metadata card —
    it describes source availability, not fabricated market data.
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

    if page_snippet:
        raw_text = (
            "SEBI Registered Investment Advisor (RIA) Registry — "
            "official registry of SEBI-licensed, fiduciary-duty investment advisors "
            "who are legally accountable for advice given to retail investors. "
            f"Page content excerpt: {page_snippet}"
        )
    else:
        raw_text = (
            "SEBI Registered Investment Advisor (RIA) Registry — "
            "official registry maintained by SEBI of licensed RIAs who operate "
            "under a fiduciary duty and are legally accountable for investment advice. "
            "Registry URL: https://www.sebi.gov.in/sebiweb/other/OtherAction.do"
            "?doRecognisedFpi=yes&intmId=13 (fetch unavailable at harvest time)."
        )

    card = _make_card(
        source_type=source_type,
        source_name=source_name,
        source_url=source_url,
        title="SEBI Registered Investment Advisor Registry",
        raw_text=raw_text,
        tickers=[],
    )
    logger.info("SEBI RIA Registry: 1 card (fetch_ok=%s)", bool(page_snippet))
    return [card]


# ═══════════════════════════════════════════════════════════════════════════
# Source 5: AMFI Mutual Fund Data (reference card)
# ═══════════════════════════════════════════════════════════════════════════

def _scrape_amfi_nav_data() -> list[dict]:
    """
    Emit ONE reference card summarising AMFI NAV data availability.
    Emitted even on fetch failure.
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

    if summary_detail:
        raw_text = (
            "AMFI (Association of Mutual Funds in India) publishes daily mutual-fund "
            "NAV data for all schemes registered in India. This is a key macro data "
            "source for tracking AUM flows, redemptions, and fund-manager positioning "
            "across equity, debt, and hybrid categories. "
            + summary_detail
        )
    else:
        raw_text = (
            "AMFI (Association of Mutual Funds in India) publishes daily NAV data "
            "for all registered mutual-fund schemes in India via NAVAll.txt. "
            "Data is used to track aggregate AUM, FII/DII flows, equity MF inflows, "
            "and debt fund trends — all material macro signals for Indian equity markets. "
            "Data URL: https://www.amfiindia.com/spages/NAVAll.txt "
            "(fetch unavailable at harvest time)."
        )

    card = _make_card(
        source_type=source_type,
        source_name=source_name,
        source_url=source_url,
        title="AMFI India — Mutual Fund NAV & AUM Data",
        raw_text=raw_text,
        tickers=[],
    )
    logger.info("AMFI MF Data: 1 card (detail_ok=%s)", bool(summary_detail))
    return [card]


# ═══════════════════════════════════════════════════════════════════════════
# Public API
# ═══════════════════════════════════════════════════════════════════════════

_MIN_CREDIBILITY = 5


def scrape_all_expert_sources() -> list[dict]:
    """Run all five expert sources, return combined RAW card dicts.

    Filters out anything with credibility_score < 5. NEVER raises.
    """
    all_cards: list[dict] = []

    sources = [
        ("credit_rating_agencies", _scrape_all_rating_agencies),
        ("cnbc_expert_views", _scrape_cnbc_expert_views),
        ("moneycontrol_expert_columns", _scrape_moneycontrol_expert_columns),
        ("sebi_ria_registry", _scrape_sebi_ria_registry),
        ("amfi_nav_data", _scrape_amfi_nav_data),
    ]

    for name, scrape_fn in sources:
        try:
            cards = scrape_fn()
            all_cards.extend(cards)
        except Exception as exc:
            logger.warning("Source '%s' raised unexpectedly: %s", name, exc)

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
