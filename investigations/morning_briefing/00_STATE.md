# Morning Briefing Investigation — State Tracker

**Investigation opened:** 2026-06-16  
**Lead:** Incident Response Engineer  
**Status:** FIXES IN PROGRESS

---

## Milestones

| # | Milestone | Status |
|---|-----------|--------|
| 1 | Read all system maps (01–05) | ✅ DONE |
| 2 | Trace backend source: router, snapshot, harvest_worker, cache_service, disk_cache | ✅ DONE |
| 3 | Trace iOS source: NetworkManager, HomeScreen, WatchlistModels | ✅ DONE |
| 4 | Compile findings (06) | ✅ DONE |
| 5 | Root cause analysis (07) | ✅ DONE |
| 6 | Fix plan (08) | ✅ DONE |
| 7 | Implement all fixes | ✅ DONE |
| 8 | Implementation report (09) | ✅ DONE |
| 9 | Final state update | ✅ DONE |

---

## Bugs Found (Summary)

| ID | Severity | Component | Description |
|----|----------|-----------|-------------|
| B1 | CRITICAL | backend/services/disk_cache.py | Cache invalidation is a no-op in async context — Redis never cleared |
| B2 | HIGH | backend/services/harvest_worker.py | Scheduler timezone Asia/Dubai causes 4h drift — pregen fires 2:30 AM IST not 6:30 AM IST |
| B3 | HIGH | backend/routers/portfolio.py | `extra_body` Anthropic misuse causes live-gen to fail on every cache miss |
| B4 | MEDIUM | backend/services/harvest_worker.py | `_run_evaluate_analysis_outcomes` registered twice (duplicate job) |
| B5 | MEDIUM | backend/services/portfolio_snapshot.py | Pregen writes cache with no TTL (24h) vs endpoint 2h — inconsistency |
| B6 | MEDIUM | backend/services/portfolio_snapshot.py | DB session held open across all yfinance calls in user loop |
| B7 | MEDIUM | ios/Views/HomeScreen.swift | "READ FULL BRIEF" button has no action (dead button) |
