# Modular Architecture Migration Ledger

## Phase 0: Immutable State Tracking & Reversibility
- [x] Create backup: `main.py` → `main_legacy_backup.py`
- [ ] Git commit: `chore: snapshot before modular migration`

## Phase 1: Router Module Creation
- [ ] Create `routers/` directory with `__init__.py`
- [ ] Migrate `routers/auth.py` — `/login`, `/register`
- [ ] Migrate `routers/portfolio.py` — `/portfolio/*`, `/trade-journal/*`
- [ ] Migrate `routers/market.py` — `/market-indices`, `/api/v1/market/*`
- [ ] Migrate `routers/analysis.py` — `/analyze`, `/quick-info`, `/dashboard-data`
- [ ] Migrate `routers/alerts.py` — `/alerts/*`
- [ ] Migrate `routers/user.py` — `/users`, `/watchlist/*`, `/notifications/*`

## Phase 2: main.py Orchestration Rewrite
- [ ] Strip relocated endpoints from main.py
- [ ] Import and register all routers with `app.include_router()`
- [ ] Preserve CORS, middleware, scheduler, health endpoint

## Phase 3: Compilation & Parity Verification
- [ ] Boot uvicorn server locally
- [ ] Test `/health` endpoint
- [ ] Test `/api/v1/market/dashboard-pulse` endpoint

## Phase 4: State Archiving
- [ ] Check off all items in migration_ledger.md
- [ ] Git commit: `refactor: modularized monolithic backend into domain-driven APIRouters`
