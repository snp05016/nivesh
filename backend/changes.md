# Changes Log — YouTube SEBI-Only Channel Registry

**Date**: June 3, 2026  
**Task**: Replace 5 non-SEBI YouTube channels with 6 verified SEBI-registered channels + portfolio personalised feed

---

## Summary

| Metric | Before | After |
|--------|--------|-------|
| YouTube channels | 5 (non-SEBI) | 6 (SEBI-registered) |
| Videos in DB | 25 | 83 |
| Harvest sources | channel_harvest only | channel_harvest + ytdlp_search |
| Home feed | Chronological 8 videos | 2-tier: portfolio-matched first, general fill |
| New DB columns | — | `channel_url`, `harvested_at`, `matched_ticker`, `source`, `sebi_reg` |

---

## SEBI Channel Registry (Sacred)

| Channel | SEBI Reg | Entity |
|---------|----------|--------|
| SOIC | INH000012582 | SOIC Intelligent Research LLP |
| Basant Maheshwari | INH000017949 | Basant Maheshwari Wealth Advisers LLP |
| Capitalmind | INH000014003 | Capitalmind Research LLP |
| Anand Rathi | INH000000834 | Anand Rathi Share and Stock Brokers Ltd |
| Motilal Oswal | INH000000412 | Motilal Oswal Financial Services Ltd |
| Yadnya Investment Academy | INH000008349 | Yadnya Academy Pvt. Ltd. |

---

## Files Modified

### `services/youtube_harvester.py` — Full Rewrite
- **Old**: Simple scraper fetching 5 non-SEBI channels via yt-dlp only
- **New**: Dual-path (YouTube Data API v3 primary, yt-dlp fallback), SEBI-only registry, portfolio harvest function, `_upsert_video()` dedup logic, `get_company_name()` ticker→company lookup, `TICKER_COMPANY_MAP` for 30 NSE stocks

### `database.py` — YouTubeVideo Model Extended
- Added `channel_url` (String, nullable)
- Added `harvested_at` (DateTime, default=utcnow)
- Added `matched_ticker` (String, nullable, indexed)
- Added `source` (String, default="channel_harvest")
- Added `sebi_reg` (String, nullable)

### `main.py` — Pipeline + Home Feed
- **Scheduler**: Added `harvest_portfolio_videos` at 1:15 AM IST (15 min after channel sweep)
- **Home Feed** (`/api/v1/home-feed`): Rewrote YouTube section with 2-tier ranking:
  - Tier 1: Videos matching user's portfolio tickers (last 7 days)
  - Tier 2: General SEBI channel videos to fill remaining 8 slots
  - Deduplication by `video_id` across both tiers
  - New fields in `serialize_video`: `matched_ticker`, `source`, `sebi_reg`

---

## Local Database Changes (SQLite)

```sql
ALTER TABLE youtube_videos ADD COLUMN channel_url TEXT;
ALTER TABLE youtube_videos ADD COLUMN harvested_at TIMESTAMP;
ALTER TABLE youtube_videos ADD COLUMN matched_ticker TEXT;
ALTER TABLE youtube_videos ADD COLUMN source TEXT DEFAULT 'channel_harvest';
ALTER TABLE youtube_videos ADD COLUMN sebi_reg TEXT;
CREATE INDEX ix_yt_matched_ticker ON youtube_videos (matched_ticker);
```

Old non-SEBI rows deleted (Shankar Sharma, Asset Yogi, Akshat Shrivastava — 15 rows removed).

---

## Pipeline Schedule (IST)

| Time | Job | Description |
|------|-----|-------------|
| 12:30 AM | `harvest_news` | News articles from MoneyControl/ET |
| 1:00 AM | `harvest_youtube_metadata` | Channel sweep: 6 SEBI channels × 6 videos |
| 1:15 AM | `harvest_portfolio_videos` | Ticker search: each portfolio holding × 3 videos |
| 1:30 AM | `harvest_all_advisors` | Advisor insight scraping |
| 2:00 AM | `evaluate_analysis_outcomes` | Outcome evaluation |
| 4:30 PM | `snapshot_all_users` | Portfolio valuation snapshot |
| 4:45 PM | `run_nightly_screen` | PKScreener screening |

---

## Manual Test Results (Local)

- **Channel harvest**: 6/6 channels, 13 new videos added ✓
- **Portfolio harvest**: 17 tickers processed, 47 videos added ✓
- **Dedup**: 0 duplicates in DB ✓
- **SEBI compliance**: All 36 channel videos have `sebi_reg` populated ✓
- **Syntax check**: All 3 Python files compile clean ✓

---

## Server Deploy Steps

1. Copy modified files to server:
   ```bash
   scp backend/services/youtube_harvester.py root@165.22.221.18:/root/nivesh/stocks/services/
   scp backend/database.py root@165.22.221.18:/root/nivesh/stocks/
   scp backend/main.py root@165.22.221.18:/root/nivesh/stocks/
   ```

2. Run migration on server:
   ```bash
   ssh root@165.22.221.18 "cd /root/nivesh/stocks && venv/bin/python3 -c \"
   import sqlite3
   conn = sqlite3.connect('stockapp.db')
   c = conn.cursor()
   cols = {row[1] for row in c.execute('PRAGMA table_info(youtube_videos)').fetchall()}
   for name, typ in [('channel_url','TEXT'),('harvested_at','TIMESTAMP'),('matched_ticker','TEXT'),('source','TEXT'), ('sebi_reg','TEXT')]:
       if name not in cols:
           c.execute('ALTER TABLE youtube_videos ADD COLUMN ' + name + ' ' + typ)
   c.execute('CREATE INDEX IF NOT EXISTS ix_yt_matched_ticker ON youtube_videos (matched_ticker)')
   conn.commit()
   conn.close()
   print('Migration done')
   \""
   ```

3. Restart service:
   ```bash
   ssh root@165.22.221.18 "systemctl restart nivesh"
   ```

4. Verify:
   ```bash
   curl -s http://localhost:8000/api/v1/home-feed?user_id=1 | python3 -m json.tool | head -50
   ```

---

## Dev Mode: Manual YouTube Harvest

**Added**: June 3, 2026

### Backend
- `POST /api/v1/admin/harvest-youtube` — Triggers both channel + portfolio harvest on demand. Admin-only (JWT required).
- Returns `channel_harvest` and `portfolio_harvest` result objects.

### iOS
- `NetworkManager.triggerYouTubeHarvest()` — Calls the admin endpoint.
- `SettingsScreen` dev tools (triple-tap "NIVESH OFFICIAL TOLDER v1.0"): New row "HARVEST YOUTUBE NOW" that triggers harvest and shows toast with results.

### How to use
1. Open Settings → triple-tap the footer text to reveal dev tools
2. Tap "HARVEST YOUTUBE NOW"
3. Wait for toast: "Harvest done: X channel + Y portfolio videos"

---

## Deploy Status

- **Deployed**: June 3, 2026
- **Server DB**: 87 YouTube videos (36 channel harvest + 51 portfolio search)
- **Service**: Active (PID 96336)
- **All 6 SEBI channels**: Harvested and verified
- **Home-feed**: 2-tier ranking working (portfolio-matched first)
