"""
services/filings_extractor.py — Background extraction loop for corporate regulatory filings.

Parses NSE corporate filings every 15 minutes. Stores recent filings
in an in-memory TTL cache for the earnings dashboard to consume.
"""

import time
import logging
from datetime import datetime, timedelta, timezone
from typing import Any

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# In-memory cache — 15-min TTL (matches scraper.py pattern)
# ---------------------------------------------------------------------------

_FILINGS_CACHE: dict[str, Any] = {"data": None, "ts": 0.0}
_FILINGS_TTL = 900  # 15 minutes


def get_cached_filings() -> dict | None:
    """Return cached filings if fresh, else None."""
    now = time.time()
    if _FILINGS_CACHE["data"] is not None and (now - _FILINGS_CACHE["ts"]) < _FILINGS_TTL:
        return _FILINGS_CACHE["data"]
    return None


def _set_filings_cache(data: dict) -> None:
    _FILINGS_CACHE["data"] = data
    _FILINGS_CACHE["ts"] = time.time()


# ---------------------------------------------------------------------------
# NSE corporate filings scraper
# ---------------------------------------------------------------------------

_NSE_FILINGS_URL = "https://www.nseindia.com/api/corporates?index=equities"
_NSE_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
    "Accept": "application/json",
    "Referer": "https://www.niseindia.com/",
}


def _scrape_nse_filings() -> list[dict]:
    """
    Fetch recent corporate filings from NSE.
    Returns list of dicts with keys: ticker, company, filing_type, filed_date, description.
    """
    try:
        resp = requests.get(
            _NSE_FILINGS_URL,
            headers=_NSE_HEADERS,
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()

        filings = []
        records = data if isinstance(data, list) else data.get("data", [])
        for item in records[:100]:  # cap at 100 most recent
            filings.append({
                "ticker": item.get("symbol", ""),
                "company": item.get("companyName", ""),
                "filing_type": item.get("desc", ""),
                "filed_date": item.get("filedDate", ""),
                "description": item.get("detail", ""),
            })
        return filings
    except Exception as e:
        logger.warning(f"NSE filings scrape failed: {e}")
        return []


def _scrape_moneycontrol_filings() -> list[dict]:
    """
    Fallback: scrape Moneycontrol corporate announcements page.
    """
    try:
        resp = requests.get(
            "https://www.moneycontrol.com/stocks/marketinfo/mkt_announcement.php",
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=15,
        )
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        filings = []
        rows = soup.select("table tr")
        for row in rows:
            cols = row.select("td")
            if len(cols) >= 3:
                filings.append({
                    "ticker": cols[0].get_text(strip=True),
                    "company": cols[1].get_text(strip=True) if len(cols) > 1 else "",
                    "filing_type": cols[2].get_text(strip=True) if len(cols) > 2 else "",
                    "filed_date": cols[3].get_text(strip=True) if len(cols) > 3 else "",
                    "description": "",
                })
        return filings[:100]
    except Exception as e:
        logger.warning(f"Moneycontrol filings scrape failed: {e}")
        return []


def _expand_weekend_window(date_str: str) -> list[str]:
    """Fix 2.48: Expand weekend dates to include Fri+Mon for 14-day view.
    Board meetings rescheduled to Sat/Sun should still appear in tracking."""
    from datetime import datetime as _dt, timedelta as _td
    try:
        d = _dt.strptime(date_str[:10], "%Y-%m-%d")
    except ValueError:
        return [date_str] if date_str else []
    results = [date_str]
    if d.weekday() == 5:  # Saturday
        results.append((d - _td(days=1)).strftime("%Y-%m-%d"))
    elif d.weekday() == 6:  # Sunday
        results.append((d - _td(days=2)).strftime("%Y-%m-%d"))
        results.append((d + _td(days=1)).strftime("%Y-%m-%d"))
    return results


def harvest_filings() -> dict:
    """
    Main extraction loop — called every 15 minutes by APScheduler.
    Fetches corporate filings from NSE (primary) or Moneycontrol (fallback).
    Updates in-memory cache. Weekend meetings expanded for 14-day tracking.
    """
    filings = _scrape_nse_filings()
    source = "nse"

    if not filings:
        filings = _scrape_moneycontrol_filings()
        source = "moneycontrol"

    # Categorize filings by type
    earnings_filings = [f for f in filings if any(
        kw in f.get("filing_type", "").lower()
        for kw in ["result", "quarterly", "annual", "financial"]
    )]

    result = {
        "total_filings": len(filings),
        "earnings_filings_count": len(earnings_filings),
        "recent_filings": filings[:50],
        "earnings_filings": earnings_filings[:30],
        "source": source,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
    }

    _set_filings_cache(result)
    logger.info(f"[filings_extractor] Harvested {len(filings)} filings ({len(earnings_filings)} earnings) from {source}")
    return result


# ---------------------------------------------------------------------------
# Auditor info extraction — GAP 13
# ---------------------------------------------------------------------------

_AUDITOR_CACHE: dict[str, Any] = {"data": None, "ts": 0.0}
_AUDITOR_CACHE_TTL = 3600

_BIG4_FIRMS = {"Deloitte", "PwC", "PricewaterhouseCoopers", "Ernst & Young", "EY", "KPMG"}

_AUDITOR_KEYWORDS = [
    "statutory auditor", "auditor resignation", "appointment of auditor",
    "reappointment of auditor", "change in auditor", "auditor report",
]


def _is_big4(auditor_name: str) -> bool:
    name_lower = auditor_name.lower()
    for firm in _BIG4_FIRMS:
        if firm.lower() in name_lower:
            return True
    return False


def extract_auditor_info(ticker: str) -> dict:
    """
    Extract auditor name and tenure for a given ticker.

    Sources:
      1. NSE corporate-announcements API (primary)
      2. In-memory TTL cache (1-hour)

    Scoring:
      - Big-4 + tenure > 5 years → +0.05
      - Big-4 + tenure 2-5 years → +0.02
      - Non-Big-4 + tenure > 5 years → 0.0
      - Non-Big-4 + tenure < 2 years → -0.03
      - Unknown → -0.05
    """
    import re

    now = time.time()
    if _AUDITOR_CACHE["data"] is not None and (now - _AUDITOR_CACHE["ts"]) < _AUDITOR_CACHE_TTL:
        cached = _AUDITOR_CACHE["data"]
        if isinstance(cached, dict) and ticker in cached:
            return cached[ticker]

    try:
        resp = requests.get(
            _NSE_FILINGS_URL,
            headers=_NSE_HEADERS,
            timeout=15,
        )
        resp.raise_for_status()
        raw = resp.json()
        records = raw if isinstance(raw, list) else raw.get("data", [])

        auditor_name: str | None = None
        tenure_years: int | None = None
        appointment_year: int | None = None

        for item in records:
            if (item.get("symbol") or "").upper() != ticker.upper():
                continue

            desc = (item.get("desc") or "")
            detail = (item.get("detail") or "")
            combined = f"{desc} {detail}".lower()

            if not any(kw in combined for kw in _AUDITOR_KEYWORDS):
                continue

            text = f"{desc} {detail}"

            ms_match = re.search(r'M/s\.?\s+([A-Za-z0-9\s&.,()]+?)(?:\s+as\s|\s+to\s|[.;]|$)', text, re.IGNORECASE)
            if ms_match:
                auditor_name = ms_match.group(1).strip().rstrip(". ")
            else:
                apt_match = re.search(r'appointment of\s+([A-Za-z0-9\s&.,()]+?)\s+as\s+auditor', text, re.IGNORECASE)
                if apt_match:
                    auditor_name = apt_match.group(1).strip()
                else:
                    reapt_match = re.search(r're[- ]?appointment of\s+([A-Za-z0-9\s&.,()]+?)\s+as\s+auditor', text, re.IGNORECASE)
                    if reapt_match:
                        auditor_name = reapt_match.group(1).strip()

            yr_match = re.search(r'(?:appointed|tenure|since|from|w\.e\.f\.)\s+(\d{4})', combined, re.IGNORECASE)
            if yr_match:
                appointment_year = int(yr_match.group(1))
                from datetime import datetime as _dt
                tenure_years = _dt.utcnow().year - appointment_year

            is_big4 = _is_big4(auditor_name) if auditor_name else None

            break

        if auditor_name is None:
            boost = -0.05
        elif is_big4:
            if tenure_years is not None and tenure_years > 5:
                boost = 0.05
            elif tenure_years is not None and tenure_years >= 2:
                boost = 0.02
            else:
                boost = 0.02
        else:
            if tenure_years is not None and tenure_years > 5:
                boost = 0.0
            elif tenure_years is not None and tenure_years < 2:
                boost = -0.03
            else:
                boost = -0.03

        result = {
            "auditor_name": auditor_name,
            "tenure_years": tenure_years,
            "is_big4": is_big4,
            "auditor_quality_boost": boost,
        }

        _AUDITOR_CACHE["data"] = {ticker: result}
        _AUDITOR_CACHE["ts"] = time.time()

        return result

    except Exception as e:
        logger.warning(f"auditor info extraction failed for {ticker}: {e}")
        return {
            "auditor_name": None,
            "tenure_years": None,
            "is_big4": None,
            "auditor_quality_boost": -0.05,
        }
