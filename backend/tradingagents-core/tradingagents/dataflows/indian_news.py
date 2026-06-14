"""Indian market news fetcher.

Three sources — all free, no API keys needed:

1. Moneycontrol RSS  — general market + filtered by ticker/company name
2. Economic Times RSS — markets + stocks sections
3. NSE corporate announcements — direct from nseindia.com API
   (requires a short session init to get cookies, standard practice)

Returns formatted plaintext blocks ready for prompt injection.
Degrades gracefully — never raises, always returns a string.
"""

from __future__ import annotations

import html
import logging
import re
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from typing import Optional
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import requests

logger = logging.getLogger(__name__)

_UA_RSS = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)

# ---------------------------------------------------------------------------
# RSS helpers
# ---------------------------------------------------------------------------

MONEYCONTROL_FEEDS = [
    "https://www.moneycontrol.com/rss/latestnews.xml",
    "https://www.moneycontrol.com/rss/marketreports.xml",
    "https://www.moneycontrol.com/rss/results.xml",
]

ET_FEEDS = [
    "https://economictimes.indiatimes.com/markets/stocks/rss.cms",
    "https://economictimes.indiatimes.com/markets/rss.cms",
    "https://economictimes.indiatimes.com/industry/rss.cms",
]


def _clean_html(text: str) -> str:
    if not text:
        return ""
    text = re.sub(r"<[^>]+>", " ", text)
    return " ".join(html.unescape(text).split())


def _fetch_rss(url: str, timeout: float = 8.0) -> list[ET.Element]:
    """Fetch an RSS feed, return list of <item> elements."""
    try:
        req = Request(url, headers={"User-Agent": _UA_RSS})
        with urlopen(req, timeout=timeout) as resp:
            root = ET.fromstring(resp.read())
        channel = root.find("channel")
        return channel.findall("item") if channel is not None else []
    except Exception as exc:
        logger.warning("RSS fetch failed for %s: %s", url, exc)
        return []


def _item_text(item: ET.Element) -> tuple[str, str, str]:
    """Return (title, description, pub_date) from an RSS <item>."""
    title = _clean_html((item.findtext("title") or "").strip())
    desc = _clean_html((item.findtext("description") or "").strip())
    if len(desc) > 300:
        desc = desc[:300] + "…"
    pub = (item.findtext("pubDate") or "").strip()
    return title, desc, pub


def _matches(text: str, keywords: list[str]) -> bool:
    t = text.lower()
    return any(kw in t for kw in keywords)


def _search_keywords(ticker: str) -> list[str]:
    """Build keyword list from ticker — handles common name variants."""
    base = ticker.split(".")[0].upper()
    variants = [base.lower()]

    # Known short-name → full-name mappings for popular Indian tickers
    _MAP = {
        "HDFCBANK": ["hdfc bank", "hdfcbank"],
        "ICICIBANK": ["icici bank", "icicibank"],
        "KOTAKBANK": ["kotak bank", "kotakbank"],
        "SBIN": ["state bank", "sbi"],
        "BAJFINANCE": ["bajaj finance"],
        "BAJAJFINSV": ["bajaj finserv"],
        "HINDUNILVR": ["hindustan unilever", "hul"],
        "BHARTIARTL": ["bharti airtel", "airtel"],
        "ADANIENT": ["adani enterprises"],
        "ADANIPOWER": ["adani power"],
        "ADANIPORTS": ["adani ports"],
        "TATAMOTORS": ["tata motors"],
        "TATASTEEL": ["tata steel"],
        "TATAPOWER": ["tata power"],
        "SUNPHARMA": ["sun pharma", "sun pharmaceutical"],
        "DRREDDY": ["dr reddy", "dr. reddy"],
        "BAJAJ-AUTO": ["bajaj auto"],
        "HEROMOTOCO": ["hero motocorp", "hero moto"],
        "IRFC": ["irfc", "indian railway finance"],
        "POWERGRID": ["power grid"],
        "COALINDIA": ["coal india"],
        "DMART": ["dmart", "avenue supermarts"],
        "IRCTC": ["irctc", "indian railway catering"],
    }
    if base in _MAP:
        variants = list(set(variants + _MAP[base]))
    return variants


# ---------------------------------------------------------------------------
# Moneycontrol
# ---------------------------------------------------------------------------

def fetch_moneycontrol_news(ticker: str, max_items: int = 8) -> str:
    keywords = _search_keywords(ticker)
    matched: list[tuple[str, str, str]] = []

    for feed_url in MONEYCONTROL_FEEDS:
        for item in _fetch_rss(feed_url):
            title, desc, pub = _item_text(item)
            if _matches(title + " " + desc, keywords):
                matched.append((title, desc, pub))
        if len(matched) >= max_items:
            break

    matched = matched[:max_items]
    if not matched:
        return f"<Moneycontrol: no recent articles found for {ticker.split('.')[0].upper()}>"

    lines = [f"Moneycontrol — {len(matched)} recent articles:"]
    for title, desc, pub in matched:
        lines.append(f"  [{pub[:16]}] {title}")
        if desc:
            lines.append(f"    {desc}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Economic Times
# ---------------------------------------------------------------------------

def fetch_et_news(ticker: str, max_items: int = 8) -> str:
    keywords = _search_keywords(ticker)
    matched: list[tuple[str, str, str]] = []

    for feed_url in ET_FEEDS:
        for item in _fetch_rss(feed_url):
            title, desc, pub = _item_text(item)
            if _matches(title + " " + desc, keywords):
                matched.append((title, desc, pub))
        if len(matched) >= max_items:
            break

    matched = matched[:max_items]
    if not matched:
        return f"<Economic Times: no recent articles found for {ticker.split('.')[0].upper()}>"

    lines = [f"Economic Times — {len(matched)} recent articles:"]
    for title, desc, pub in matched:
        lines.append(f"  [{pub[:16]}] {title}")
        if desc:
            lines.append(f"    {desc}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# NSE corporate announcements
# ---------------------------------------------------------------------------

_NSE_BASE = "https://www.nseindia.com"
_NSE_ANNOUNCE = "/api/corp-info?symbol={sym}&corpType=announcement&market=capital"
_NSE_HEADERS = {
    "User-Agent": _UA_RSS,
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.nseindia.com/",
    "X-Requested-With": "XMLHttpRequest",
}


def _nse_session() -> requests.Session:
    """Bootstrap a session with NSE cookies (required for their API)."""
    s = requests.Session()
    s.headers.update(_NSE_HEADERS)
    try:
        s.get(_NSE_BASE, timeout=8)
        s.get(f"{_NSE_BASE}/get-quotes/equity?symbol=NIFTY", timeout=5)
    except Exception:
        pass
    return s


def fetch_nse_announcements(ticker: str, max_items: int = 10) -> str:
    sym = ticker.split(".")[0].upper()
    try:
        session = _nse_session()
        url = _NSE_BASE + _NSE_ANNOUNCE.format(sym=sym)
        resp = session.get(url, timeout=10)
        resp.raise_for_status()
        data = resp.json()

        announcements = (
            data.get("corpInfo", [])
            or data.get("data", [])
            or (data if isinstance(data, list) else [])
        )

        if not announcements:
            return f"<NSE corporate announcements: none found for {sym}>"

        lines = [f"NSE Corporate Announcements — {sym} (latest {min(len(announcements), max_items)}):"]
        for item in announcements[:max_items]:
            subject = (
                item.get("subject")
                or item.get("desc")
                or item.get("announcement")
                or str(item)
            )
            dt = item.get("bcastDt") or item.get("date") or ""
            lines.append(f"  [{dt[:10]}] {_clean_html(str(subject))[:200]}")
        return "\n".join(lines)

    except Exception as exc:
        logger.warning("NSE announcements fetch failed for %s: %s", sym, exc)
        return f"<NSE corporate announcements: unavailable for {sym} ({exc})>"


# ---------------------------------------------------------------------------
# Combined entry point
# ---------------------------------------------------------------------------

def fetch_indian_market_news(ticker: str) -> str:
    """Fetch Moneycontrol + Economic Times + NSE announcements for ticker.

    Called instead of Reddit for Indian stocks. Returns a single formatted
    plaintext block ready for LLM prompt injection.
    """
    parts = []

    mc = fetch_moneycontrol_news(ticker)
    parts.append(mc)

    et = fetch_et_news(ticker)
    parts.append(et)

    nse = fetch_nse_announcements(ticker)
    parts.append(nse)

    return "\n\n".join(parts)
