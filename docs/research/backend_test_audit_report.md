# Backend Test Audit Report

Last verified: 2026-06-16
Repository: `/Users/saumya/Desktop/nivesh`
Prompt: `prompts/TEST_BACKEND_PROMPT.md`

## Executive Summary

I removed the obsolete looping `backend/tests/test_api.py` and added a new offline backend contract suite covering FastAPI route inventory, API contracts, database constraints, migration metadata, financial calculations, and concurrency guards.

New focused tests:

- `backend/tests/test_backend_contract_api.py`
- `backend/tests/test_backend_contract_routes.py`
- `backend/tests/test_backend_contract_database.py`
- `backend/tests/test_backend_contract_db_integrity.py`
- `backend/tests/test_backend_contract_migrations.py`
- `backend/tests/test_backend_contract_migration_metadata.py`
- `backend/tests/test_backend_contract_financial.py`
- `backend/tests/test_backend_contract_concurrency.py`

Test infra change:

- `backend/pytest.ini` registers the existing `timeout` marker.

Current score: **88 / 100**.

The backend local suite is now green. The major schema/API/migration regressions found by the audit were fixed, stale legacy expectations were updated to match current async/auth contracts, and the hardcoded remote E2E suite is now opt-in via `NIVESH_LIVE_E2E_BASE_URL`.

## Verification Commands

```bash
cd /Users/saumya/Desktop/nivesh/backend
.venv/bin/python3 -m pytest tests/test_backend_contract_*.py -q
```

Result: **49 passed, 48 warnings**.

```bash
cd /Users/saumya/Desktop/nivesh/backend
.venv/bin/python3 -m pytest tests -q
```

Result: **237 passed, 49 skipped, 169 warnings**.

The 49 skipped tests are live E2E checks in `backend/tests/test_e2e_api.py`; they run only when `NIVESH_LIVE_E2E_BASE_URL` is set.

```bash
cd /Users/saumya/Desktop/nivesh/backend
DATABASE_URL=sqlite:////tmp/nivesh_alembic_contract.db .venv/bin/alembic check
```

Result: **No new upgrade operations detected.**

Alembic now honors `DATABASE_URL`, so disposable migration checks do not mutate `stockapp.db`.

## Adversarial Loops

Loop 1, route inventory:

- Built a FastAPI `app.routes` inventory and pinned critical mixed-prefix paths such as `/login`, `/analyze`, `/portfolio/{user_id}`, `/market-indices`, `/api/v1/home-feed`, `/api/v1/options/payoff`, and `/harvester/feed`.
- Added `test_critical_route_inventory_matches_current_fastapi_app`.
- Gap found: old tests and docs still assume stale route behavior.

Loop 2, database invariants:

- Tested table creation, required fields, unique constraints, FK enforcement, cascade behavior, Decimal precision, and duplicate prevention.
- Added strict regression tests for schema defects before fixing them.
- Gaps found and fixed: watchlist sentinel conflicts with `Portfolio` checks, `PortfolioValuationHistory.user_id` lacks FK, duplicate `AnalysisHistory` JSON columns existed in source.

Loop 3, migrations:

- Tested one-base/one-head revision graph, missing down revisions, upgrade/downgrade function presence, destructive operation visibility, bytecode-only migration detection, and env config.
- Added a temporary-config lifecycle test for `upgrade head`, `downgrade -1`, `upgrade head`, and `check`.
- Gaps found and fixed: Alembic ignored `DATABASE_URL`; stale bytecode remained for deleted revision `4fcaaf510069`; base revision failed on an empty DB; `alembic check` reported drift.

Loop 4, services/failure/concurrency:

- Added deterministic financial tests for options payoff and stress-test logic.
- Added concurrency tests for `_acquire_analysis_slot`, stale slot eviction, idempotent release, and job registry reaping.
- Full-suite run found and fixed legacy failures caused by MagicMocked heavy services, stale staleness expectations, auth assumptions, and Decimal/schema drift.

## Resolved High-Severity Issues

### 1. Watchlist API is broken by Portfolio check constraints

Files:

- `backend/models/db_models.py`
- `backend/routers/user.py`

`Portfolio` documents watchlist rows as `shares=0` and `buy_price=0`, and `/watchlist/add` creates exactly those sentinel values. The table now has:

```python
CheckConstraint("shares > 0", name="ck_portfolio_shares_positive")
CheckConstraint("buy_price > 0", name="ck_portfolio_buy_price_positive")
```

Impact: `/watchlist/add` returns `500` for valid watchlist requests.

Regression tests:

- `test_watchlist_add_accepts_documented_zero_value_sentinel`
- `test_watchlist_add_uses_documented_sentinel_values`
- `test_watchlist_zero_sentinel_matches_model_documentation`

Status: fixed and covered by passing contract tests.

### 2. Portfolio listing breaks after Numeric/Decimal migration

File:

- `backend/routers/portfolio.py`

`GET /portfolio/{user_id}` mixes `float` accumulators with SQLAlchemy `Decimal` values. Current failure:

```text
unsupported operand type(s) for +=: 'float' and 'decimal.Decimal'
```

Impact: valid holdings can be created/updated/deleted, but listing the portfolio can return `500`.

Regression test:

- `test_portfolio_listing_handles_decimal_money_columns`

Status: fixed and covered by passing contract tests.

### 3. Alembic ignores DATABASE_URL

Files:

- `backend/alembic.ini`
- `backend/migrations/env.py`

`alembic.ini` hardcodes `sqlite:///./stockapp.db`. `env.py` uses `config.get_main_option("sqlalchemy.url")` and does not read `DATABASE_URL`.

Impact: commands that appear to target disposable databases can mutate `stockapp.db`; CI cannot safely inject a test DB URL.

Regression test:

- `test_migration_env_honors_database_url_environment_override`

Status: fixed and covered by passing contract tests.

### 4. Alembic check reported schema drift

Command:

```bash
DATABASE_URL=sqlite:////tmp/nivesh_alembic_contract.db .venv/bin/alembic check
```

Status: fixed. `alembic upgrade head`, `alembic downgrade -1`, `alembic upgrade head`, and `alembic check` pass against disposable SQLite databases.

### 5. Migration source/bytecode mismatch

File deleted from source but present in bytecode:

- `backend/migrations/versions/4fcaaf510069_add_missing_models_and_columns.py`
- `backend/migrations/versions/__pycache__/4fcaaf510069_add_missing_models_and_columns.cpython-314.pyc`

Impact: local Alembic state can become confusing; bytecode-only revisions should not exist in migration directories.

Regression test:

- `test_alembic_bytecode_revisions_have_matching_source_files`

Status: fixed. The stale bytecode file was removed.

### 6. Base migration is not a full empty-database schema

File:

- `backend/migrations/versions/0dc3e605ea33_initial_schema.py`

The base revision performs delta operations and does not create all current model tables. It is not a reliable empty database bootstrap migration. With a temporary Alembic config pointed at an empty SQLite database, `upgrade head` fails immediately:

```text
sqlite3.OperationalError: no such index: ix_market_anomalies_anomaly_type
```

Regression test:

- `test_base_revision_creates_current_model_tables`
- `test_alembic_empty_database_lifecycle`

Status: fixed. The base migration now bootstraps the current ORM schema, and later placeholder revisions preserve the source revision chain.

### 7. Duplicate AnalysisHistory column declarations

File:

- `backend/models/db_models.py`

`AnalysisHistory` declares `quantitative_drivers` and `tail_risk_flags` twice with conflicting JSON defaults.

Regression test:

- `test_model_source_has_no_duplicate_column_assignments`

Status: fixed and covered by passing source-contract tests.

### 8. PortfolioValuationHistory has no user FK

File:

- `backend/models/db_models.py`

`PortfolioValuationHistory.user_id` is `nullable=False` and indexed but has no `ForeignKey("users.id")`.

Impact: orphan valuation rows are possible.

Regression test:

- `test_portfolio_valuation_history_rejects_orphan_user_id`

Status: fixed and covered by FK rejection tests.

## Existing Suite Status

Full command:

```bash
cd /Users/saumya/Desktop/nivesh/backend
.venv/bin/python3 -m pytest tests -q
```

Failed: **0** locally.

Resolved clusters:

- `tests/test_backend_tasks.py`: imports real `services.scraper`; cache testability restored with `_TTL_SECONDS` and `TTLLRUCache.clear()`, and fuzzy aliases now cover RELIANCE/TATAMOTORS cases.
- `tests/test_calibration_engine.py`: imports real `services.staleness`; 3-day-old analyses now reach the STALE threshold.
- `tests/test_comprehensive.py`: updated to accept current async `202` analysis jobs, protected-route `401`s, removed alert-check route `404`, and hardened sector performance against malformed provider data.
- `tests/test_e2e_api.py`: hardcoded remote server removed from default local suite; live E2E is opt-in via `NIVESH_LIVE_E2E_BASE_URL`.
- `tests/test_engine_bounds.py`: now enforces AGENTS.md one-round debate config and current token caps.
- `tests/test_extreme_enrichers.py`: factor scoring now supports missing peer/trend context gracefully.

## Route Inventory

Route inventory source: FastAPI `app.routes` on 2026-06-16.

| Route | Methods | Router file | Function | DB tables/services touched | Existing tests | Missing tests | Priority |
|---|---|---|---|---|---|---|---|
| `/login` | POST | `backend/routers/auth.py` | `login_endpoint` | `users`, JWT | contract auth tests | password edge cases, rate-limit | High |
| `/register` | POST | `backend/routers/auth.py` | `register_endpoint` | `users`, rate limiter | contract duplicate tests | rollback on create failure | High |
| `/analyze` | POST | `backend/routers/analysis.py` | `analyze_endpoint` | `analysis_jobs`, cache, job manager | contract async job tests, existing analysis tests | subprocess failure matrix, paid API isolation | Critical |
| `/analyze/job/{job_id}` | GET | `backend/routers/analysis.py` | `get_job_status` | `analysis_jobs` | existing job tests | cross-user status checks | High |
| `/analyze/{job_id}/cancel` | POST | `backend/routers/analysis.py` | `cancel_job_endpoint` | `analysis_jobs`, job registry | existing job tests | missing job, already finished job | High |
| `/analyze/active` | GET | `backend/routers/analysis.py` | `get_active_job` | `analysis_jobs` | route inventory | auth/ownership matrix | Medium |
| `/analyze/batch` | POST | `backend/routers/analysis.py` | `batch_analyze_endpoint` | `analysis_jobs` | existing batch tests | duplicate/rate-limit boundary | High |
| `/quick-info` | GET | `backend/routers/analysis.py` | `quick_info_endpoint` | yfinance/cache | route inventory | provider failure schema | High |
| `/api/v1/home-feed` | GET | `backend/routers/analysis.py` | `get_home_feed` | analysis/news/market services | route inventory | cache hit/miss, text contract | High |
| `/api/v1/technical-signals` | GET | `backend/routers/analysis.py` | `get_technical_signals` | technical service/cache | route inventory | invalid ticker, provider failure | Medium |
| `/portfolio/{user_id}` | GET | `backend/routers/portfolio.py` | `portfolio_endpoint` | `portfolio`, yfinance, analysis | contract Decimal regression fixed | cross-user, provider failure | Critical |
| `/portfolio/add`, `/portfolio` | POST | `backend/routers/portfolio.py` | `portfolio_add_endpoint` | `portfolio`, cache invalidate | contract CRUD tests | DB rollback on provider failure | Critical |
| `/portfolio/remove` | DELETE | `backend/routers/portfolio.py` | `portfolio_remove_endpoint` | `portfolio` | contract CRUD tests | cross-user not-found matrix | High |
| `/portfolio/update` | PUT | `backend/routers/portfolio.py` | `portfolio_update_endpoint` | `portfolio`, yfinance | contract CRUD tests | Decimal totals regression after fix | High |
| `/portfolio/note` | PUT | `backend/routers/portfolio.py` | `portfolio_note_endpoint` | `portfolio` | contract CRUD tests | holdings vs watchlist conflict | Medium |
| `/watchlist/add` | POST | `backend/routers/user.py` | `watchlist_add_endpoint` | `portfolio`, yfinance/cache | sentinel regression fixed | duplicate/cross-user after schema fix | Critical |
| `/watchlist/{user_id}` | GET | `backend/routers/user.py` | `watchlist_get_endpoint` | `portfolio`, analysis history, yfinance | sentinel regression fixed | provider failure shape | Critical |
| `/watchlist/remove` | DELETE | `backend/routers/user.py` | `watchlist_remove_endpoint` | `portfolio` | route inventory | not-found, cross-user | High |
| `/alerts/add` | POST | `backend/routers/alerts.py` | `alerts_add_endpoint` | `price_targets` | contract invalid input tests | trigger behavior, duplicate policy | High |
| `/alerts/{user_id}` | GET | `backend/routers/alerts.py` | `alerts_get_endpoint` | `price_targets`, yfinance | existing failing e2e | provider failure schema | High |
| `/alerts/remove` | DELETE | `backend/routers/alerts.py` | `alerts_remove_endpoint` | `price_targets` | route inventory | cross-user delete | High |
| `/trade-journal` | POST | `backend/routers/portfolio.py` | `trade_journal_add_endpoint` | `trade_journal` | contract CRUD tests | rollback/failure injection | High |
| `/trade-journal/{user_id}` | GET | `backend/routers/portfolio.py` | `trade_journal_get_endpoint` | `trade_journal`, users | contract CRUD tests | cross-user matrix | High |
| `/trade-journal/{entry_id}` | PUT/DELETE | `backend/routers/portfolio.py` | update/delete | `trade_journal` | contract CRUD tests | stale ownership tests | High |
| `/market-indices` | GET | `backend/routers/market.py` | `market_indices_endpoint` | market provider/cache | existing comprehensive tests | deterministic fallback tests | High |
| `/search` | GET | `backend/routers/market.py` | `search_endpoint` | ticker directory/provider | route inventory | fuzzy/empty/oversized queries | High |
| `/sector-performance` | GET | `backend/routers/market.py` | `sector_performance_endpoint` | yfinance/provider | existing failing test | provider exception handling | High |
| `/api/v1/stock-profile` | GET | `backend/routers/market.py` | `stock_profile_endpoint` | yfinance/provider | route inventory | schema validation, missing data | High |
| `/api/v1/market/stock-history` | GET | `backend/routers/market.py` | `stock_history_endpoint` | yfinance/NSE provider | route inventory | invalid date/range | Medium |
| `/api/v1/market/pulse` | GET | `backend/routers/market.py` | `market_pulse_endpoint` | scraper/cache | route inventory | cache hit/miss with real fake cache | High |
| `/api/v1/market/momentum` | GET | `backend/routers/market.py` | `market_momentum_endpoint` | scraper/cache | route inventory | fallback schema | Medium |
| `/api/v1/market/dashboard` | GET | `backend/routers/market.py` | `market_dashboard_endpoint` | market services | existing comprehensive tests | provider failure matrix | Medium |
| `/api/v1/earnings/*` | GET/POST/DELETE | `backend/routers/market.py`, `earnings_surprise.py` | earnings endpoints | earnings tables/services | route inventory, partial existing tests | alert ownership, DB rollback, date bounds | High |
| `/api/v1/ideas/*` | GET | `backend/routers/market.py` | ideas endpoints | advisor/news services | route inventory | empty DB and provider failure | Medium |
| `/api/v1/copilot/chat` | POST | `backend/routers/copilot.py` | `copilot_chat` | copilot service/LLM | route inventory | no paid API, invalid prompt | High |
| `/api/v1/screener/natural-language` | POST | `backend/routers/nl_screener.py` | `natural_language_screener` | NL screener/LLM | route inventory | no paid API, invalid NL | High |
| `/api/v1/portfolio/stress-test` | POST | `backend/routers/stress_test.py` | `portfolio_stress_test` | stress service | financial service tests | route input schema | Medium |
| `/api/v1/market/sector-rotation` | GET | `backend/routers/sector_rotation.py` | `get_sector_rotation` | sector service | route inventory | provider failure schema | Medium |
| `/portfolio/correlation` | GET | `backend/routers/correlation.py` | `get_portfolio_correlation` | correlation service | route inventory | deterministic matrix | Medium |
| `/api/v1/options/payoff` | POST | `backend/routers/options_strategy.py` | `compute_strategy_payoff` | options service | financial service tests | route schema invalid legs | High |
| `/api/v1/options/chain/{ticker}` | GET | `backend/routers/market.py` | `get_option_chain_metrics_endpoint` | options scraper | route inventory | provider failure | Medium |
| `/harvester/*` | GET/POST | `backend/routers/harvester.py` | harvester endpoints | separate harvester DB/services | route inventory | auth/admin, source health, scrape failure | High |
| Admin/error routes | GET/POST | `backend/routers/*`, `backend/services/harvest_worker.py` | admin endpoints | error tables/harvest services | route inventory | admin auth, no live side effects | Medium |
| Static/docs/health routes | GET | `backend/main.py`, FastAPI internals | health/docs | DB health | existing health tests | liveness DB failure | Low |

All remaining effective routes are covered by the route inventory contract test, but many are not yet covered with behavioral success/failure tests.

## Database Inventory

Current ORM tables:

- `advisor_biographies`
- `advisor_insights`
- `analysis_history`
- `analysis_jobs`
- `block_deals`
- `device_tokens`
- `earnings_alerts`
- `earnings_error_logs`
- `earnings_surprise_history`
- `fii_dii_flow`
- `ideas_error_logs`
- `macro_events`
- `market_anomalies`
- `market_error_logs`
- `net_worth_ledger`
- `news_articles`
- `notification_error_logs`
- `pkscreener_signals`
- `portfolio`
- `portfolio_valuation_history`
- `price_targets`
- `signal_events`
- `text_advisory_insights`
- `trade_journal`
- `users`
- `youtube_videos`

Tested directly:

- creation via `Base.metadata`
- user FK rejection on `Portfolio` and `PriceTarget`
- `User` cascade to portfolio, analysis history, price targets, trade journal
- unique constraints on portfolio and ledger snapshots
- Decimal precision round trips
- duplicate username rejection
- `get_session()` rollback

Untested or partially tested:

- every external harvest table needs provider-specific fixtures
- `AdvisorInsight`/`TextAdvisoryInsight` relationship deletion behavior
- error log insertion helpers swallow exceptions by design and need targeted monkeypatch tests
- Postgres-specific Numeric/index behavior remains unverified locally

## Migration Inventory

Current source migrations:

- `0dc3e605ea33_initial_schema.py`
- `323c66c5ca0e_auto.py`
- `1ad82d60efcc_convert_float_to_numeric_for_precision.py`

Deleted source no longer visible in bytecode:

- `4fcaaf510069_add_missing_models_and_columns.py`

Revision chain:

- base: `0dc3e605ea33`
- next: `323c66c5ca0e`
- head: `1ad82d60efcc`

Tests added:

- one base and one head
- down revisions exist
- every migration has upgrade/downgrade
- base migration bootstraps current ORM schema
- follow-on placeholder revisions preserve revision history without destructive drift
- env uses model metadata and SQLite batch mode
- env URL override, bytecode-only revision, empty-database lifecycle, downgrade/upgrade roundtrip, and `alembic check`

## Service/Financial Inventory

Tested directly:

- `services.options_engine.compute_options_payoff`
- `services.options_engine` invalid input validation
- `services.stress_test.get_sector`
- `services.stress_test.run_stress_test`
- `core.concurrency` analysis slot locking
- `services.job_manager.reap_finished`

Still needs tests:

- `services.correlation_engine.compute_portfolio_correlation`
- `services.quant_engine`
- `services.confidence_engine`
- `services.factor_engine`
- `services.extreme_enrichers`
- `services.llm_utils` no-western-scale and JSON normalization contracts beyond existing tests
- additional scraper provider failure matrices beyond cache/fallback smoke coverage
- `services.harvester_db` separate schema lifecycle

## Recommendations

1. Add Postgres-backed migration/constraint tests in CI because SQLite cannot prove all production DB behavior.
2. Add behavioral route-family tests for harvester, market dashboard, earnings, copilot, NL screener, sector rotation, correlation, and options route input validation.
3. Run live E2E explicitly with `NIVESH_LIVE_E2E_BASE_URL` after deployment and update any remote-only auth assumptions there.
4. Replace `datetime.utcnow()` usage with timezone-aware calls to reduce warning noise.
5. Replace the current metadata bootstrap migration with explicit `op.create_table` operations if production migration auditability becomes a release requirement.

## Completion Notes

The local backend suite is passing. The remaining gap is environment coverage: live E2E is intentionally skipped unless `NIVESH_LIVE_E2E_BASE_URL` is provided, and Postgres migration behavior is not proven by the local SQLite suite.
