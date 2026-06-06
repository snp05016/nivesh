# Nivesh Backend — Agent Navigation Map

> Generated: 2026-06-06
> Monolith refactor complete. All structural modules mapped below.

## Quick Reference

| What | Where |
|------|-------|
| **App entrypoint** | `main.py` — CORS, middleware, router includes, health probes |
| **Pydantic schemas** | `schemas/` — `auth.py`, `portfolio.py`, `market.py` |
| **Auth / Security** | `core/security.py` — `get_current_user_id`, `require_auth`, `require_admin` |
| **Background harvesters** | `services/harvest_worker.py` — YouTube, Advisor, News + APScheduler |
| **YFinance helpers** | `services/nse_data_provider.py` — `resolve_ticker`, `fetch_info`, `fetch_price`, `to_ns` |
| **Database ORM** | `database.py` — SQLAlchemy models + `get_session()` |
| **Shared utilities** | `helpers.py` — dashboard state, rate limiter, auth (re-exports), yfinance helpers (re-exports) |

## Directory Layout

```
backend/
  ├── main.py                    # App config entrypoint (~1839 lines)
  ├── database.py                # SQLAlchemy ORM + session management
  ├── helpers.py                 # Shared utilities, dashboard state, re-exports
  ├── prompts.py                 # AI system prompts
  ├── portfolio_charts.py        # Chart generation
  │
  ├── core/
  │   ├── __init__.py
  │   └── security.py            # JWT auth dependencies
  │
  ├── schemas/
  │   ├── __init__.py            # Re-exports all schemas
  │   ├── auth.py                # LoginRequest, RegisterRequest
  │   ├── portfolio.py           # AnalyzeRequest, Watchlist*, Portfolio*, Alert*, TradeJournal*
  │   └── market.py              # IndexSnapshot, BreadthData, DashboardPulseResponse, etc.
  │
  ├── services/
  │   ├── harvest_worker.py      # Background harvesters + APScheduler (NEW)
  │   ├── nse_data_provider.py   # NSE data abstraction + yfinance helpers (ENHANCED)
  │   ├── orchestrator.py        # LangGraph AI orchestration
  │   ├── advisor_harvester.py   # Advisor content harvesting
  │   ├── news_harvester.py      # News content harvesting
  │   ├── youtube_harvester.py   # YouTube content harvesting
  │   ├── scraper.py             # Web scraping / Firecrawl
  │   ├── disk_cache.py          # L2 persistent cache
  │   ├── error_telemetry.py     # Error tracking + CorrelationID middleware
  │   ├── feedback_injector.py   # AI feedback loop
  │   ├── sentiment_engine.py    # Sentiment analysis
  │   ├── factor_engine.py       # Factor analysis
  │   ├── piotroski.py           # Piotroski F-Score
  │   ├── pkscreener_runner.py   # PK Screener
  │   ├── portfolio_snapshot.py  # Portfolio snapshots
  │   ├── filings_extractor.py   # Corporate filings
  │   ├── options_scraper.py     # Options data
  │   ├── staleness.py           # Cache staleness scoring
  │   ├── ticker_matcher.py      # Ticker name matching
  │   └── transcript_engine.py   # Earnings transcripts
  │
  └── routers/
      ├── __init__.py
      ├── alerts.py              # Price alert CRUD
      ├── analysis.py            # AI analysis endpoints
      ├── auth.py                # Login/register
      ├── dashboard.py           # SSE live dashboard
      ├── market.py              # Market data, indices, fundamentals
      ├── notifications.py       # Push notification registration
      ├── portfolio.py           # Portfolio CRUD, export, morning brief
      └── user.py                # Profile, watchlist, device tokens
```

## Key Import Chains

### Auth Flow
```
routers/*.py  →  helpers.py  →  get_current_user_id / require_auth / require_admin
                              →  core/security.py (canonical definitions)
```

### Dashboard State Flow
```
main.py (middleware, /dashboard-data)
  └── Uses LOCAL copies of _dash_lock, _harvest_status, etc.

services/harvest_worker.py
  └── Imports from helpers.py (_dash_update_harvest, _dash_lock, _harvest_status)

routers/*.py
  └── Import from helpers.py (shared state)
```

### Schema Flow
```
routers/*.py  →  helpers.py  →  schemas/*.py (canonical definitions)
main.py       →  schemas/*.py (direct import)
```

## Refactoring History

| Phase | Commit | What |
|-------|--------|------|
| 1 | `372c080` | Schemas extracted to `schemas/` |
| 2 | `09e92b4` | Auth moved to `core/security.py` |
| 3 | `bc24a8d` | Harvest workers moved to `services/harvest_worker.py` |
| 4 | `f15b0fb` | YFinance helpers moved to `services/nse_data_provider.py` |
| 5 | `4bb266a` | main.py minimized, dead code removed |
