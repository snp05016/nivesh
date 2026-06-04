# Modular Architecture Migration Ledger

## Phase 0: Immutable State Tracking & Reversibility
- [x] Create backup: `main.py` → `main_legacy_backup.py`
- [x] Git commit: `chore: snapshot before modular migration`

## Phase 1: Router Module Creation
- [x] Create `routers/` directory with `__init__.py`
- [x] Migrate `routers/auth.py` — `/login`, `/register` (2 endpoints)
- [x] Migrate `routers/portfolio.py` — `/portfolio/*`, `/trade-journal/*` (24 endpoints)
- [x] Migrate `routers/market.py` — `/market-indices`, `/api/v1/market/*` (26 endpoints)
- [x] Migrate `routers/analysis.py` — `/analyze`, `/quick-info`, `/dashboard-data` (9 endpoints)
- [x] Migrate `routers/alerts.py` — `/alerts/*` (4 endpoints)
- [x] Migrate `routers/user.py` — `/users`, `/watchlist/*`, `/notifications/*` (9 endpoints)
- [x] Create `routers/dashboard.py` — `/api/v1/dashboard/stream` (SSE live updates)

## Phase 2: main.py Orchestration Rewrite
- [x] Strip relocated endpoints from main.py (7430 → 2884 lines)
- [x] Import and register all routers with `app.include_router()`
- [x] Preserve CORS, middleware, scheduler, health endpoint
- [x] Add admin harvest endpoints (youtube, advisors, news)

## Phase 3: Compilation & Parity Verification
- [x] Boot uvicorn server locally
- [x] Test `/health` endpoint
- [x] Test `/api/v1/market/dashboard-pulse` endpoint
- [x] Run comprehensive test suite (102 tests, all passing)

## Phase 4: Additional Fixes
- [x] Fix DeepSeek model: ensure v4-flash used everywhere (not v3)
- [x] Add dashboard live updates via SSE endpoint
- [x] Create comprehensive test suite with 102 tests
- [x] Verify valuation-history works for past dates

## Phase 5: State Archiving
- [x] Check off all items in migration_ledger.md
- [x] Git commit: `refactor: modularized monolithic backend into domain-driven APIRouters`

## File Structure
```
/backend
  ├── main.py (2884 lines - entry point & app initialization)
  ├── helpers.py (530 lines - shared helpers, constants, models)
  ├── database.py (Unchanged)
  ├── prompts.py (Unchanged)
  ├── services/ (Existing harvesting & AI logic)
  └── routers/ (NEW - 6 domain routers + dashboard)
      ├── __init__.py
      ├── auth.py (42 lines - 2 endpoints)
      ├── portfolio.py (2488 lines - 24 endpoints)
      ├── market.py (1161 lines - 26 endpoints)
      ├── analysis.py (1187 lines - 9 endpoints)
      ├── alerts.py (170 lines - 4 endpoints)
      ├── user.py (368 lines - 9 endpoints)
      └── dashboard.py (53 lines - 1 SSE endpoint)
```

## Test Results
- **Total Tests:** 102
- **Passed:** 102
- **Failed:** 0
- **Warnings:** 38 (deprecation warnings, non-critical)
