# Final Monolith Refactor — Task Checklist

> Started: 2026-06-06
> Status: COMPLETE

## Phases

- [x] **Phase 1**: Create `schemas/` directory and extract Pydantic models
  - [x] `schemas/__init__.py` — re-exports all models
  - [x] `schemas/auth.py` — LoginRequest, RegisterRequest
  - [x] `schemas/portfolio.py` — 11 request models
  - [x] `schemas/market.py` — 9 response models
  - [x] Updated `main.py` to import from schemas/

- [x] **Phase 2**: Create `core/security.py` with JWT auth
  - [x] `core/__init__.py`
  - [x] `core/security.py` — get_current_user_id, require_auth, require_admin
  - [x] Updated `main.py` to import from core.security

- [x] **Phase 3**: Create `services/harvest_worker.py`
  - [x] Background runners: _run_youtube_harvest_bg, _run_advisor_harvest_bg, _run_news_harvest_bg
  - [x] APScheduler setup with all 8 nightly cron jobs
  - [x] Admin harvest trigger endpoints (FastAPI router)
  - [x] start_scheduler() / stop_scheduler() lifecycle functions
  - [x] Updated `main.py` to import from harvest_worker

- [x] **Phase 4**: Move yfinance helpers to `services/nse_data_provider.py`
  - [x] Added resolve_ticker(), fetch_info(), fetch_price(), to_ns()
  - [x] Added EXCHANGE_SUFFIX and NSE ticker lookup tables
  - [x] Removed dead yfinance helper code from main.py

- [x] **Phase 5**: Minimize main.py
  - [x] Removed dead EXCHANGE_SUFFIX, NSE_TICKERS, NSE_TICKER_OVERRIDES
  - [x] Cleaned up stale comment blocks
  - [x] Reduced from 2221 → 1839 lines

- [x] **Phase 6**: Boot test and fix import errors
  - [x] `from main import app` — OK, 99 routes registered
  - [x] No ImportError, NameError, or ModuleNotFoundError

- [x] **Section 5**: Agent Map Archiving
  - [x] Created `AGENT_MAP.md` in backend root
  - [x] Created `tasks_final_refactor.md` (this file)

## Files Created

| File | Lines | Purpose |
|------|-------|---------|
| `schemas/__init__.py` | 25 | Re-exports all Pydantic models |
| `schemas/auth.py` | 12 | Authentication schemas |
| `schemas/portfolio.py` | 101 | Portfolio/trading schemas |
| `schemas/market.py` | 70 | Market data response schemas |
| `core/__init__.py` | 1 | Core package marker |
| `core/security.py` | 35 | JWT auth dependencies |
| `services/harvest_worker.py` | 180 | Background harvesters + APScheduler |
| `AGENT_MAP.md` | ~100 | Agent navigation index |

## Files Modified

| File | Change |
|------|--------|
| `main.py` | -382 lines: removed inline schemas, auth, harvesters, yfinance helpers |
| `services/nse_data_provider.py` | +80 lines: added yfinance helpers |

## Verification

```bash
cd backend && .venv/bin/python -c "from main import app; print('OK, routes:', len(app.routes))"
# Output: OK, routes: 99
```

## Git History

```
4bb266a refactor: minimized main.py into a clean app configuration entrypoint
f15b0fb refactor: centralized low-level yfinance tickers under nse_data_provider
bc24a8d refactor: isolated background task runners from core application server
09e92b4 refactor: moved JWT auth verification layers out of main.py
372c080 refactor: decoupled Pydantic data contracts into dedicated schemas namespace
```
