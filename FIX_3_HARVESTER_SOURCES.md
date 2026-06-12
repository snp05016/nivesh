# FIX #3: Harvester Sources — Debug & Fix All Expert Scrapers

Paste into Claude Code. Execute without asking questions.

## PROBLEM

The harvester is live on port 8001 with 10 sources, but 8 show 0 items scraped:
- CRISIL Ratings: 0 items
- ICRA Ratings: 0 items
- CARE Ratings: 0 items
- India Ratings: 0 items
- CNBC-TV18: 0 items
- Moneycontrol: 0 items
- YouTube: 0 items

Only AMFI (1 item) and SEBI RIA (1 item) returned data. The RSS URLs or HTML selectors are stale.

## FIX: Debug Each Source One at a Time

### Step 1: Add a standalone test script

Create `backend/debug_harvester_sources.py`:

```python
"""Test each harvester source individually and print what it returns."""
import sys, os, json
sys.path.insert(0, os.path.dirname(__file__))

from services.harvester_expert import (
    scrape_crisil, scrape_icra, scrape_care, scrape_india_ratings,
    scrape_cnbc_experts, scrape_moneycontrol_experts
)

sources = {
    "CRISIL": scrape_crisil,
    "ICRA": scrape_icra,
    "CARE": scrape_care,
    "India Ratings": scrape_india_ratings,
    "CNBC-TV18": scrape_cnbc_experts,
    "Moneycontrol": scrape_moneycontrol_experts,
}

for name, fn in sources.items():
    try:
        results = fn() if callable(fn) else []
        count = len(results) if isinstance(results, list) else 0
        status = "✅" if count > 0 else "❌"
        print(f"{status} {name}: {count} items")
        if count > 0 and isinstance(results, list):
            first = results[0]
            print(f"   First item: {json.dumps({k: str(v)[:120] for k, v in first.items() if k != 'raw_text'}, default=str)}")
    except Exception as e:
        print(f"💥 {name}: CRASHED — {e}")
```

Run on the server: `ssh root@165.22.221.18 "cd /root/nivesh/backend && python3 debug_harvester_sources.py"`

This tells you exactly which scraper is broken and how.

### Step 2: Fix RSS-based sources (CRISIL, ICRA, CARE, India Ratings)

These use `feedparser.parse(url)`. The URLs are likely stale.

For each, open the URL in a browser to verify it exists. Then update the constant in `harvester_expert.py`.

**Known current URLs (verify these):**
- CRISIL: `https://www.crisil.com/en/home/newsroom/rss/rating-actions.html`
- ICRA: `https://www.icra.in/RSS/RSSFeeds.aspx` 
- CARE: Check `https://www.careratings.com/` — look for RSS icon in page source (`application/rss+xml`)
- India Ratings: Check `https://www.indiaratings.co.in/` — same approach

If an RSS URL is dead, replace it with the actual current URL found on the site.

**Pattern to find RSS URLs on any site:**
```bash
curl -s https://www.careratings.com/ | grep -i 'rss\|application/rss\|\.xml' | head -5
```

### Step 3: Fix HTML-based sources (CNBC-TV18, Moneycontrol)

These use `requests.get()` + regex to extract article links, then scrape each article.

**Common failure modes:**

A. **Article link regex stale** — the `_extract_article_links()` function in `harvester_expert.py` looks for URLs containing "article", "story", "news", "opinion". If the site changed their URL pattern, it returns nothing.

B. **Article text extraction stale** — `_extract_article_text()` searches for `<article>`, `<div class="art-body">`, etc. If the site redesigned, these selectors fail.

**Debug approach for each source:**

```bash
# Fetch the listing page and see what the actual HTML looks like
ssh root@165.22.221.18
cd /root/nivesh/backend
python3 -c "
import requests
headers = {'User-Agent': 'Mozilla/5.0 (compatible; NiveshHarvester/1.0)'}
# CNBC
resp = requests.get('https://www.cnbctv18.com/market/stocks/', headers=headers, timeout=15)
# Find all article links
import re
links = re.findall(r'href=\"([^\"]*/(?:article|story|news)[^\"]*)\"', resp.text, re.IGNORECASE)
print(f'CNBC links found: {len(links)}')
for l in links[:5]:
    print(f'  {l}')
"
```

If links=0, the URL pattern changed. Update `_extract_article_links()` or the source URL in `harvester_expert.py`.

### Step 4: Fix YouTube harvester

Check if the YouTube Data API key is set and valid:
```bash
ssh root@165.22.221.18 "grep YOUTUBE_API_KEY /root/nivesh/backend/.env"
```

If the key is missing or expired, get a new one from Google Cloud Console (free tier: 10,000 quota units/day). Enable the "YouTube Data API v3".

### Step 5: Rerun the debug script

After each fix, rerun `debug_harvester_sources.py` to confirm the source returns data. Then trigger a full scrape:
```bash
curl -X POST "http://localhost:8001/harvester/trigger/scrape?source=expert&limit=10"
```

Check `curl http://localhost:8001/harvester/sources` — all sources should show `items_scraped > 0` and `is_healthy: true`.

## VERIFY

1. All 9 expert sources show `is_healthy: true` on `/harvester/sources`
2. At least 5 sources show `items_scraped > 0`
3. `/harvester/feed?limit=10` returns reformatted cards with credibility scores

## DO NOT
- Don't change the card storage pipeline (`harvester_db.py`)
- Don't change the reformatter (`harvester_reformatter.py`) 
- Don't add new dependencies unless unavoidable
- Don't fix all sources at once — fix CRISIL first (highest signal), verify, then move to next
- If a source is fundamentally broken (site paywalled, requires login), mark it as `is_healthy: false` and skip it rather than spending hours
