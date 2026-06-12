# FIX #2: NSE/BSE Scraper — Replace with ScraperAPI Dual-Exchange

Paste into Claude Code. Execute without asking questions.

## PROBLEM

DigitalOcean IPs are blocked by NSE at the network level. No header hack fixes this. BSE uses the same CDN infrastructure and may block DO IPs now or later. Direct scraping from a DO droplet is unreliable for Indian exchanges.

## FIX: ScraperAPI Free Tier → scrapes BOTH NSE and BSE

ScraperAPI (https://scraperapi.com) has a free tier: 1000 requests/month, zero credit card, auto-rotates residential IPs. It proxies your HTTP requests through clean residential IPs that exchanges don't block.

**End result:** One API key, two exchanges working reliably.

## IMPLEMENTATION

### Step 1: Get ScraperAPI key (do this BEFORE running code)

1. Go to https://scraperapi.com/signup
2. Sign up for free tier (no credit card)
3. Copy your API key from the dashboard
4. Add to server: `echo "SCRAPERAPI_KEY=your_key_here" >> /root/nivesh/backend/.env`

### Step 2: Replace FILE backend/services/harvester_sebi.py

Rewrite the entire file. The old code had NSE RSS only. The new code has NSE + BSE, both routed through ScraperAPI.

```python
"""
SEBI / Exchange filings harvester — NSE + BSE via ScraperAPI.

Uses ScraperAPI free tier (1000 reqs/month) to route requests through
residential IPs that Indian exchanges don't block.

Public: harvest_sebi_filings(limit=30) -> int
"""

from __future__ import annotations

import json
import hashlib
import logging
import os
import re
import time as _time
from datetime import datetime
from typing import Optional

import requests
from bs4 import BeautifulSoup

from services.harvester_db import get_session as h_get_session, upsert_card, record_source_health

logger = logging.getLogger("harvester.sebi")

# ═══════════════════════════════════════════════════════════════════════
# ScraperAPI config
# ═══════════════════════════════════════════════════════════════════════

_SCRAPERAPI_KEY = os.environ.get("SCRAPERAPI_KEY", "")
_SCRAPERAPI_URL = "http://api.scraperapi.com"

def _scraper_get(url: str, timeout: int = 30) -> requests.Response:
    """Fetch a URL through ScraperAPI residential proxy."""
    params = {
        "api_key": _SCRAPERAPI_KEY,
        "url": url,
        "country_code": "in",  # route through Indian residential IP
        "render": "false",      # no JS rendering needed for RSS/HTML tables
    }
    return requests.get(_SCRAPERAPI_URL, params=params, timeout=timeout)


# ═══════════════════════════════════════════════════════════════════════
# NSE — HTML announcements page (more reliable than RSS)
# ═══════════════════════════════════════════════════════════════════════

NSE_ANNOUNCEMENTS_URL = (
    "https://www.nseindia.com/companies-listing/"
    "corporate-filings-announcements?tabIndex=equity"
)
SOURCE_NAME_NSE = "NSE Corporate Announcements"


# ═══════════════════════════════════════════════════════════════════════
# BSE — corporate announcements page  
# ═══════════════════════════════════════════════════════════════════════

BSE_ANNOUNCEMENTS_URL = (
    "https://www.bseindia.com/corporates/ann.aspx?expandable=0"
)
SOURCE_NAME_BSE = "BSE Corporate Announcements"


# ═══════════════════════════════════════════════════════════════════════
# Governance keywords (same as before — unchanged)
# ═══════════════════════════════════════════════════════════════════════

GOVERNANCE_KEYWORDS = [
    "resignation of statutory auditor",
    "resignation of auditor",
    "auditor resignation",
    "resignation of managing director",
    "resignation of chief executive",
    "resignation of chief financial",
    "resignation of cfo",
    "pledge", "pledged shares", "invocation of pledge",
    "sebi order", "sebi action", "sebi investigation",
    "insider trading", "sast disclosure",
    "bulk deal", "block deal",
    "credit rating downgrade", "rating downgrade",
    "delay in filing", "penalty imposed",
    "forensic audit", "related party transaction",
]

INDIAN_TICKER_PATTERN = re.compile(r'\b([A-Z]{2,20})\b')

STOPWORDS = {
    "THE", "AND", "FOR", "LTD", "LIMITED", "INDIA", "NSE", "BSE", "SEBI",
    "RBI", "FROM", "WITH", "THAT", "THIS", "HAVE", "WERE", "WILL", "INR",
    "USD", "CR", "FY", "Q1", "Q2", "Q3", "Q4", "H1", "H2", "RS", "IS", "BE",
    "NOT", "ARE", "HAS", "HAD", "ITS", "ALSO", "PER", "DUE", "VIA",
}


# ═══════════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════════

def _extract_tickers(text: str) -> list[str]:
    found = INDIAN_TICKER_PATTERN.findall(text or "")
    return list(set(t for t in found if t not in STOPWORDS and len(t) >= 3))

def _check_governance(text: str) -> bool:
    text_lower = text.lower()
    return any(kw in text_lower for kw in GOVERNANCE_KEYWORDS)

def _make_external_id(url: str, title: str) -> str:
    return hashlib.sha256(f"{url}|{title}".encode()).hexdigest()[:40]


# ═══════════════════════════════════════════════════════════════════════
# Scrapers
# ═══════════════════════════════════════════════════════════════════════

def _scrape_exchange_html(url: str, source_name: str, table_id: str, 
                          limit: int) -> list[dict]:
    """Generic scraper for NSE/BSE HTML announcement tables."""
    try:
        resp = _scraper_get(url, timeout=45)
        if resp.status_code != 200:
            logger.warning(f"[sebi] {source_name}: HTTP {resp.status_code}")
            return []

        soup = BeautifulSoup(resp.text, "html.parser")
        
        # Try multiple table selectors
        table = (
            soup.find("table", {"id": table_id}) or
            soup.find("table", class_=lambda c: c and "announce" in c.lower()) or
            soup.find("table", class_=lambda c: c and "corporate" in c.lower()) or
            soup.find("table")  # last resort: first table on page
        )
        
        if not table:
            logger.warning(f"[sebi] {source_name}: no table found in HTML")
            # Log snippet for debugging
            logger.info(f"[sebi] {source_name}: page snippet: {soup.get_text()[:500]}")
            return []

        rows = table.find_all("tr")[1:limit+1]
        results = []
        
        for row in rows:
            cols = row.find_all("td")
            if len(cols) < 3:
                continue
            
            # Extract what we can — column order varies by exchange
            texts = [c.get_text(strip=True) for c in cols]
            full_text = " | ".join(texts)
            
            # Find any link in the row
            link = ""
            for c in cols:
                a = c.find("a")
                if a and a.get("href"):
                    link = a.get("href")
                    if not link.startswith("http"):
                        # Make absolute
                        base = url.split("/companies")[0] if "/companies" in url else "https://www.nseindia.com"
                        link = base + link if link.startswith("/") else link
                    break
            
            title = texts[1] if len(texts) > 1 else texts[0]
            
            results.append({
                "title": title[:500],
                "link": link,
                "raw_text": full_text[:5000],
                "company": texts[0] if texts else "",
            })
        
        logger.info(f"[sebi] {source_name}: scraped {len(results)} rows")
        return results
        
    except Exception as e:
        logger.error(f"[sebi] {source_name} scrape failed: {e}")
        return []


def _store_cards(results: list[dict], source_name: str, source_type: str, 
                 session) -> int:
    """Store scraped items as HarvestedCards. Returns count of new cards."""
    new_count = 0
    
    for item in results:
        external_id = _make_external_id(item.get("link", ""), item.get("title", ""))
        tickers = _extract_tickers(item.get("raw_text", "") + " " + item.get("company", ""))
        is_gov = _check_governance(item.get("raw_text", ""))
        
        try:
            was_new = upsert_card(session, {
                "external_id": external_id,
                "source_type": source_type,
                "source_name": source_name,
                "source_url": item.get("link", ""),
                "original_author": item.get("company", ""),
                "published_at": datetime.utcnow().isoformat(),
                "title": item.get("title", ""),
                "raw_text": item.get("raw_text", ""),
                "tickers": json.dumps(tickers),
                "credibility_score": 10,
                "card_type": "GOVERNANCE" if is_gov else "NEWS",
                "expert_credential": f"{source_name} — legally binding corporate disclosure",
            })
            if was_new:
                new_count += 1
        except Exception as e:
            logger.warning(f"[sebi] Failed to store card: {e}")
    
    session.commit()
    return new_count


# ═══════════════════════════════════════════════════════════════════════
# Main entry point
# ═══════════════════════════════════════════════════════════════════════

def harvest_sebi_filings(limit: int = 30) -> int:
    """Scrape NSE + BSE corporate announcements. Returns total new cards."""
    
    if not _SCRAPERAPI_KEY:
        logger.error("[sebi] SCRAPERAPI_KEY not set — cannot scrape. "
                     "Get a free key at https://scraperapi.com/signup")
        return 0
    
    session = h_get_session()
    total_new = 0
    
    sources = [
        (NSE_ANNOUNCEMENTS_URL, SOURCE_NAME_NSE, "SEBI_FILING", "announcementsTable"),
        (BSE_ANNOUNCEMENTS_URL, SOURCE_NAME_BSE, "SEBI_FILING", "ctl00_ContentPlaceHolder1_gvAnnouncements"),
    ]
    
    for url, name, s_type, table_id in sources:
        try:
            results = _scrape_exchange_html(url, name, table_id, limit)
            if results:
                new = _store_cards(results, name, s_type, session)
                total_new += new
                logger.info(f"[sebi] {name}: {new} new cards stored")
                record_source_health(session, name, is_healthy=True, 
                                    items_scraped=len(results))
            else:
                record_source_health(session, name, is_healthy=False,
                                    error_message="No rows found in HTML table")
        except Exception as e:
            logger.error(f"[sebi] {name}: {e}")
            record_source_health(session, name, is_healthy=False,
                                error_message=str(e)[:500])
    
    session.close()
    return total_new
```

### Step 3: Update requirements.txt

Add `beautifulsoup4` if not already present. (ScraperAPI uses plain `requests` — no new dependency.)

### Step 4: Adjust scheduler frequency

In the scheduler, change SEBI scraping from every 15 min to every 2 hours to stay within free tier limits:

```python
# Before: IntervalTrigger(minutes=15)
# After:  IntervalTrigger(hours=2)
```

## VERIFY

```bash
# 1. Confirm key is set
ssh root@165.22.221.18 "grep SCRAPERAPI_KEY /root/nivesh/backend/.env"

# 2. Run a manual scrape
ssh root@165.22.221.18 "cd /root/nivesh/backend && python3 -c '
from services.harvester_sebi import harvest_sebi_filings
count = harvest_sebi_filings(limit=10)
print(f\"Stored {count} new filings\")
'"

# 3. Check the cards
curl http://localhost:8001/harvester/feed?limit=5 | python3 -m json.tool

# 4. Check source health
curl http://localhost:8001/harvester/sources | python3 -m json.tool | grep -A3 "NSE\|BSE"
```

## WHAT TO DO IF SCRAPERAPI DOESN'T WORK

1. The free tier may have latency (5-10s per request). That's fine — the scheduler is async.
2. If the HTML table selectors are wrong (NSE/BSE may have redesigned), the scraper logs a page snippet. Read the log, update the selectors.
3. If ScraperAPI itself is blocked by NSE (unlikely — they rotate IPs), switch `country_code` from `"in"` to `"us"` to route through US residential IPs.

## DO NOT
- Don't keep the old NSE RSS code — replace the file entirely
- Don't pay for ScraperAPI — free tier is enough
- Don't scrape more than every 2 hours — stay under 1000 reqs/month
- Don't change the governance keyword list or card storage logic
