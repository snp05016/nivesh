"""
Test each harvester source individually and print what it returns.
Usage: python3 debug_harvester_sources.py
"""

import sys
import os
import json

sys.path.insert(0, os.path.dirname(__file__))

# Load .env if present
env_file = os.path.join(os.path.dirname(__file__), ".env")
if os.path.exists(env_file):
    with open(env_file) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))

from services.harvester_expert import (
    _scrape_all_rating_agencies,
    _scrape_cnbc_expert_views,
    _scrape_moneycontrol_expert_columns,
    _scrape_rating_feed,
    _RATING_FEEDS,
)

sources = {
    "CRISIL Ratings": lambda: _scrape_rating_feed(_RATING_FEEDS[0]),
    "ICRA Ratings": lambda: _scrape_rating_feed(_RATING_FEEDS[1]),
    "CARE Ratings": lambda: _scrape_rating_feed(_RATING_FEEDS[2]),
    "India Ratings": lambda: _scrape_rating_feed(_RATING_FEEDS[3]),
    "CNBC-TV18": _scrape_cnbc_expert_views,
    "Moneycontrol": _scrape_moneycontrol_expert_columns,
}

print("=" * 60)
print("HARVESTER SOURCE DEBUG —", __import__("datetime").datetime.now().isoformat())
print("=" * 60)

for name, fn in sources.items():
    try:
        results = fn()
        count = len(results) if isinstance(results, list) else 0
        status = "✅" if count > 0 else "❌"
        print(f"{status} {name}: {count} items")
        if count > 0 and isinstance(results, list):
            first = results[0]
            safe = {k: str(v)[:120] for k, v in first.items() if k != "raw_text"}
            print(f"   First: {json.dumps(safe, default=str)}")
        else:
            print(f"   → 0 items — URL likely stale, JS-rendered, or blocked")
    except Exception as e:
        print(f"💥 {name}: CRASHED — {e}")

# Also test full aggregation
print("\n--- scrape_all_expert_sources() ---")
try:
    from services.harvester_expert import scrape_all_expert_sources
    all_cards = scrape_all_expert_sources()
    print(f"Total combined cards: {len(all_cards)}")
except Exception as e:
    print(f"CRASHED: {e}")

print("\nDone.")
