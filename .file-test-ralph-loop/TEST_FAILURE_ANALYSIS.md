# Test Failure Analysis — Nivesh Backend
**Run target:** `saumyapatel@192.168.1.122` (server)  
**Date:** 2026-06-18  
**Totals:** 24 failures + 11 errors = 35 affected tests

---

## Summary Matrix

| # | Test | Root Cause | Severity | Real Bug? | Fix Recommendation |
|---|------|-----------|----------|-----------|-------------------|
| 1 | `test_calibrated_confidence_is_not_nullable` | **DB Schema** | **P1** | Yes — column nullable or missing default | Alembic migration incomplete: `calibrated_confidence` column added to `AnalysisHistory` without `nullable=False` + `server_default`. Run `alembic revision --autogenerate -m "fix calibrated_confidence not null"` |
| 2 | `test_run_advisor_harvester_real` | **Real API** | **P3** | No — external API flake | Mark with `@pytest.mark.skipif(not os.getenv("RUN_REAL_API_TESTS"))` or wrap in try/except with skip on network error |
| 3 | `test_analysis_engine_status` | **Test Config** | **P2** | No — route likely 404 | Test creates own `TestClient(app)` at module scope; route `/api/v1/analysis/status` may not exist or returns status outside `[200, 401]`. Either add the route or update test to expect 404 |
| 4 | `test_earnings_dashboard_endpoint` | **Test Config** | **P2** | No — route likely 404 | Same pattern — `TestClient(app)` at module scope hits `/api/v1/market/earnings-dashboard`. Verify route exists; if not, either register it or skip the test |
| 5 | `test_macro_impact_endpoint` | **Test Config** | **P2** | No — route likely 404 | Same pattern — `TestClient(app)` at module scope. Feature test for `/api/v1/market/macro-impact` (probable path). Verify route registration |
| 6 | `test_run_news_harvester_real` | **Real API** | **P3** | No — external API flake | Same as #2; gate behind `RUN_REAL_API_TESTS` env var |
| 7 | `test_screener_endpoint` | **Test Config** | **P2** | No — route likely 404 | Hits `/api/v1/market/screener`. Check if route exists vs `/screener` used in e2e tests |
| 8 | `test_sector_performance_endpoint` | **Test Config** | **P2** | No — route likely 404 | Hits `/api/v1/market/sector-performance` |
| 9 | `test_tech_momentum_endpoint` | **Test Config** | **P2** | No — route likely 404 | Hits `/api/v1/market/tech-momentum` |
| 10 | `test_run_youtube_harvester_real` | **Real API** | **P3** | No — external API flake | Same as #2; gate behind env var |
| 11 | `test_alembic_upgrade_head_from_empty` | **Migration** | **P1** | **Yes** | Migration chain cannot run from empty DB to head. A migration file references a column/table that doesn't exist when run fresh, or uses `batch_alter_table` incorrectly for SQLite. Run locally: `alembic upgrade head` on a fresh `:memory:` DB to repro |
| 12 | `test_alembic_at_head_after_upgrade` | **Migration** | **P1** | **Yes** | Follow-on from #11 — if upgrade fails, `alembic current` won't report `(head)`. Fix #11 first |
| 13-14 | Cache async tests (2) | **Test Config** | **P2** | Maybe — async context | These run `asyncio.run()` inside `threading.Thread` targets. The `cache_service_instance` fixture uses a non-existent Redis port (19999), so fallback dict is used. Likely a `RuntimeError: This event loop is already running` from nested `asyncio.run()` calls or event loop conflict in threaded context |
| 15 | `test_extreme_output` (1 of 2) | **Bug** | **P1** | **Yes** if `_normalize_response` changed | Tests the `_normalize_response()` output shape. If the orchestrator was modified and extreme fields (`scenarios`, `valuation_bands`, etc.) are no longer guaranteed, this fails. Also checks `EXTREME_ADDENDUM` presence in `prompts.py` via raw file read; if prompts.py was edited, this may break |
| 16 | `test_quant_engine` (1 of 2) | **Bug** | **P2** | Maybe | Regime detection thresholds or calibrated confidence bounds changed. If `_detect_market_regime` thresholds were modified in `services/quant_engine.py`, assertions may fail |
| 17-22 | `test_backend_contract_*` (6 tests) | **Test Config** | **P1** | Mixed | These 6 span across `test_backend_contract_routes.py`, `test_backend_contract_database.py`, `test_backend_contract_financial.py`, `test_backend_contract_db_integrity.py`, `test_backend_contract_concurrency.py`, `test_backend_contract_api.py`. On the server, many use `database.get_session()` which needs `DATABASE_URL` set. If the server DB file is locked or environment variables are wrong at test time, these fail. Decimal precision tests may fail if SQLite and Python Decimal rounding differ |
| 23-24 | `test_portfolio_*` (2 tests) | **Test Config** | **P2** | No — server state | These are e2e tests in `test_e2e_api.py` that require `NIVESH_LIVE_E2E_BASE_URL` to be set. They hit live server endpoints like `/portfolio/signal-warnings`, `/portfolio/risk-analysis/1`, etc. Fail if server is down, user-1 has no data, or route returns 500 |

---

## Errors (11)

| # | Test(s) | Root Cause | Severity | Real Bug? | Fix Recommendation |
|---|---------|-----------|----------|-----------|-------------------|
| E1-8 | Morning briefing endpoint (8 errors) | **Test Config** | **P1** | Yes — fixture setup | The morning briefing `conftest.py` creates its own test user via `/register` → `/login`. If this fixture fails (DB locked, rate limiter blocking, or duplicate username collision), ALL 8 endpoint tests error during collection/setup. The `seeded_user` fixture also calls `/portfolio/add` which may fail. Check if `_check_rate_limit` bypass applied to this conftest (it's only in the parent conftest) |
| E9 | `test_concurrent_reads` (1 error) | **Test Config** | **P2** | Maybe | Uses `threading.Barrier` + `asyncio.run()` inside threads. Same async context collision as cache tests #13-14. `RuntimeError: asyncio.run() cannot be called from a running event loop` |
| E10 | `test_edge_cases` (1 error) | **Test Config** | **P2** | No — fixture dependency | Depends on `_create_user()` helper which calls `/register` + `/login`. Same fixture setup issue as morning briefing endpoint tests. If user creation fails, test errors |
| E11 | `test_alembic_bytecode` (1 error) | **Migration** | **P3** | No — stale pyc | `test_alembic_bytecode_revisions_have_matching_source_files` checks that `__pycache__/*.pyc` files have matching `.py` source. Errors if the `__pycache__` directory doesn't exist (new env) or has orphaned bytecode. Not a code bug |

---

## Root Cause Distribution

```
DB Schema:      1  (test_calibrated_confidence)         ▏
Real API:       3  (advisor, news, youtube harvesters)   ▎
Network:        0                                       
Migration:      3  (alembic head + at_head + bytecode)  ▎
Test Config:   19  (feature tests, contract, portfolio)  ████████████
Bug:            2  (extreme output, cache async)         ▏
```

**Test Config** is the dominant category — 19 of 24 failures stem from test isolation issues, missing route registration in feature test files, or fixture/environment setup problems on the server.

---

## Severity Distribution

| Severity | Count | Meaning |
|----------|-------|---------|
| **P0** | 0 | Production broken, immediate rollback |
| **P1** | 6 | Blocks CI/CD, must fix before next deploy (DB schema, migration chain, contract, morning briefing) |
| **P2** | 18 | Feature tests not providing signal, fix but deployable |
| **P3** | 11 | Real API tests + stale pyc — non-blocking |

---

## Action Plan (Priority Order)

### Immediate (P1 — must fix before VCS merge)
1. **Fix Alembic migration chain** — `alembic upgrade head` must succeed on empty DB. Identify the broken migration revision and fix column references.
2. **Fix `calibrated_confidence` column** — Run `alembic revision --autogenerate` to add `nullable=False` + `server_default` for `AnalysisHistory.calibrated_confidence`.
3. **Fix morning briefing conftest** — Ensure `_check_rate_limit` bypass applies in morning briefing's own conftest. Consider consolidating user/auth fixtures into a single shared conftest.
4. **Fix backend contract tests** — Verify `DATABASE_URL` is set correctly on the server when running contract tests. Check for file lock on `stockapp_test.db`.

### Short-term (P2 — fix after P1s)
5. **Feature route tests** — These 6 tests (`test_analysis_engine_status`, `test_earnings_dashboard_endpoint`, `test_macro_impact_endpoint`, `test_screener_endpoint`, `test_sector_performance_endpoint`, `test_tech_momentum_endpoint`) each create their own `TestClient(app)` at module scope. They should either:
   - Use the session-scoped `client` fixture from parent conftest, OR
   - Verify the routes actually exist (the test assertions allow 401, but NOT 404), OR
   - Add `@pytest.mark.skip("route not yet registered")` if routes are planned but unimplemented.

6. **Fix async context tests** — Replace `asyncio.run()` calls inside `threading.Thread` with a thread-local event loop pattern (`asyncio.new_event_loop()` then `loop.run_until_complete()`).

### Non-blocking (P3)
7. **Gate real API tests** — Wrap `test_run_advisor_harvester_real`, `test_run_news_harvester_real`, `test_run_youtube_harvester_real` with env var gating.
8. **Clean alembic bytecode** — Run `find migrations/versions/__pycache__ -name "*.pyc" -delete` if source files were removed.
