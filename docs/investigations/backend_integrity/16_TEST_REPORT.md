# Report 16 — Test Report

**Date:** 2026-06-16  
**Branch:** feat/architecture-deepening

---

## New Test Suites (Phase 2)

### tests/smoke/test_app_startup.py — 4 tests
| Test | Result |
|------|--------|
| `test_main_module_imports_without_error` | PASS |
| `test_app_object_is_fastapi_instance` | PASS |
| `test_ping_endpoint_returns_200` | PASS |
| `test_health_endpoint_returns_200` | PASS |

### tests/migrations/test_alembic_health.py — 4 tests
| Test | Result |
|------|--------|
| `test_alembic_upgrade_head_from_empty` | PASS |
| `test_alembic_at_head_after_upgrade` | PASS |
| `test_no_model_migration_drift` | PASS |
| `test_migration_head_revision_is_b2c3d4e5f6a7` | PASS |

### tests/db/test_model_integrity.py — 9 tests
| Test | Result |
|------|--------|
| `test_user_portfolio_cascade_delete` | PASS |
| `test_user_net_worth_ledger_cascade_delete` | PASS |
| `test_user_earnings_alert_cascade_delete` | PASS |
| `test_user_analysis_jobs_cascade_delete` | PASS |
| `test_portfolio_valuation_history_cascade_delete` | PASS |
| `test_analysis_job_ticker_index_exists` | PASS |
| `test_calibrated_confidence_has_server_default` | PASS |
| `test_ml_pipeline_columns_exist` | PASS |
| `test_analysis_history_composite_index` | PASS |

### tests/api/test_endpoint_contracts.py — 8 tests (was 8 errors, now 8 pass)

**Root cause of original errors:** New test file defined a module-scoped `client` fixture that conflicted with `tests/conftest.py:255 teardown_test_user` (session-scoped autouse fixture). Fixed by renaming to `api_client`.

| Test | Result |
|------|--------|
| `test_portfolio_add_request_accepts_target_price` | PASS |
| `test_portfolio_add_request_backward_compatible` | PASS |
| `test_portfolio_update_request_accepts_target_price` | PASS |
| `test_trade_journal_add_request_has_mood` | PASS |
| `test_ping_returns_200` | PASS |
| `test_openapi_schema_generates` | PASS |
| `test_no_500_on_safe_get_endpoints` | PASS |
| `test_auth_protected_routes_return_401_without_token` | PASS |

---

## Full Suite Results

```
7 failed, 338 passed, 49 skipped, 247 warnings, 11 errors
```

**Pre-existing failures (not caused by Phase 2):**
- `test_cache.py::TestCacheAsync` — async Redis mock issue, pre-existing
- `test_backend_contract_database.py::test_decimal_money_columns_*` — Float vs Decimal type dispute, pre-existing (documented in Phase 1)
- `test_backend_contract_routes.py::test_portfolio_*` — same Float/Decimal issue
- `test_backend_contract_migrations.py::test_destructive_migration_*` — audit check, pre-existing

**Pre-existing errors:**
- `tests/morning_briefing/test_endpoint.py` — fixture scope issue in pre-existing test file, not introduced by Phase 2

**Phase 2 new tests:** 25 pass, 0 fail, 0 error.
