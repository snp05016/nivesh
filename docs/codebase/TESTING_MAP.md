# Testing Map

> Last generated: 2026-06-24. Source: test file inventory and AGENTS.md execution constraints.

## Non-Negotiable Execution Constraints

- Do not run `xcodebuild`; the iOS project is reference-only for this agent.
- Do not execute backend Python files or backend pytest locally. Backend tests must run remotely on `saumyapatel@192.168.1.122` after deploy/checkout verification.
- Static source inspection, AST parsing, `git diff --check`, route extraction, and documentation generation are allowed locally.

## Test Suite Structure

| Path | Purpose | Notes |
|---|---|---|
| `backend/tests/backend_integrity_tests/` | Import/syntax/exception/runtime warning catalog integrity suite. | Run only in allowed target runtime. |
| `backend/tests/database_integrity_tests/` | Schema, relationships, migration drift, CRUD, concurrency, constraints. | Run only in allowed target runtime. |
| `backend/tests/cache_integrity_tests/` | Cache gates and concurrency dedup behavior. | Run only in allowed target runtime. |
| `backend/tests/llm_integrity_tests/` | JSON normalization, Indian formatting, prompt integrity. | Run only in allowed target runtime. |
| `backend/tests/morning_briefing/` | Morning briefing cache, scheduler, endpoint, regression tests. | Run only in allowed target runtime. |
| `backend/tests/api/` | Endpoint contract tests. | Run only in allowed target runtime. |
| `backend/tests/feature_tests/` | Feature-specific workflows such as alerts, analysis, earnings, screener, news. | Run only in allowed target runtime. |
| `backend/tests/smoke/` | Startup/ping smoke tests. | Run only in allowed target runtime. |
| `ml-engine/tests/` | Alpha158/ML pipeline tests for the microservice. | Run only in allowed target runtime. |

## Test Inventory

- `backend/tests/api/test_endpoint_contracts.py`
- `backend/tests/backend_integrity_tests/test_01_imports_circular.py`
- `backend/tests/backend_integrity_tests/test_02_syntax_lint.py`
- `backend/tests/backend_integrity_tests/test_03_exception_catalog.py`
- `backend/tests/backend_integrity_tests/test_04_sqlalchemy_exceptions.py`
- `backend/tests/backend_integrity_tests/test_05_fastapi_exceptions.py`
- `backend/tests/backend_integrity_tests/test_06_python_builtins_exceptions.py`
- `backend/tests/backend_integrity_tests/test_07_os_io_exceptions.py`
- `backend/tests/backend_integrity_tests/test_08_unicode_exceptions.py`
- `backend/tests/backend_integrity_tests/test_09_runtime_exceptions.py`
- `backend/tests/backend_integrity_tests/test_10_warning_catalog.py`
- `backend/tests/cache_integrity_tests/test_01_cache_gates.py`
- `backend/tests/cache_integrity_tests/test_02_concurrency_dedup.py`
- `backend/tests/database_integrity_tests/test_01_schema_columns.py`
- `backend/tests/database_integrity_tests/test_02_constraints.py`
- `backend/tests/database_integrity_tests/test_03_relationships.py`
- `backend/tests/database_integrity_tests/test_04_migration_drift.py`
- `backend/tests/database_integrity_tests/test_05_crud_lifecycle.py`
- `backend/tests/database_integrity_tests/test_06_session_management.py`
- `backend/tests/database_integrity_tests/test_07_concurrent_writes.py`
- `backend/tests/database_integrity_tests/test_08_null_enforcement.py`
- `backend/tests/database_integrity_tests/test_09_foreign_keys.py`
- `backend/tests/database_integrity_tests/test_10_unique_constraints.py`
- `backend/tests/database_integrity_tests/test_11_check_constraints.py`
- `backend/tests/database_integrity_tests/test_12_indexes.py`
- `backend/tests/database_integrity_tests/test_13_telemetry_tables.py`
- `backend/tests/database_integrity_tests/test_15_error_recovery.py`
- `backend/tests/db/test_model_integrity.py`
- `backend/tests/feature_tests/advisor_harvester/test_advisor_harvester.py`
- `backend/tests/feature_tests/alerts/test_alerts.py`
- `backend/tests/feature_tests/analysis_engine/test_analysis_engine.py`
- `backend/tests/feature_tests/earnings_dashboard/test_earnings_dashboard.py`
- `backend/tests/feature_tests/macro_impact/test_macro_impact.py`
- `backend/tests/feature_tests/news_feed/test_news_feed.py`
- `backend/tests/feature_tests/portfolio_calendar/test_portfolio_calendar.py`
- `backend/tests/feature_tests/screener/test_screener.py`
- `backend/tests/feature_tests/sector_performance/test_sector_performance.py`
- `backend/tests/feature_tests/tech_momentum/test_tech_momentum.py`
- `backend/tests/feature_tests/youtube_harvester/test_youtube_harvester.py`
- `backend/tests/llm_integrity_tests/test_01_json_normalization.py`
- `backend/tests/llm_integrity_tests/test_02_indian_formatting.py`
- `backend/tests/llm_integrity_tests/test_03_prompt_integrity.py`
- `backend/tests/migrations/test_alembic_health.py`
- `backend/tests/morning_briefing/test_cache.py`
- `backend/tests/morning_briefing/test_concurrency.py`
- `backend/tests/morning_briefing/test_edge_cases.py`
- `backend/tests/morning_briefing/test_endpoint.py`
- `backend/tests/morning_briefing/test_regression.py`
- `backend/tests/morning_briefing/test_scheduler.py`
- `backend/tests/smoke/test_app_startup.py`
- `backend/tests/test_ai_engine_monitor.py`
- `backend/tests/test_analysis_job.py`
- `backend/tests/test_analysis_pipeline_regressions.py`
- `backend/tests/test_analyze_api.py`
- `backend/tests/test_analyze_dedup_endpoint.py`
- `backend/tests/test_backend_contract_api.py`
- `backend/tests/test_backend_contract_concurrency.py`
- `backend/tests/test_backend_contract_database.py`
- `backend/tests/test_backend_contract_db_integrity.py`
- `backend/tests/test_backend_contract_financial.py`
- `backend/tests/test_backend_contract_migration_metadata.py`
- `backend/tests/test_backend_contract_migrations.py`
- `backend/tests/test_backend_contract_routes.py`
- `backend/tests/test_backend_tasks.py`
- `backend/tests/test_calibration_engine.py`
- `backend/tests/test_checkpoints.py`
- `backend/tests/test_comprehensive.py`
- `backend/tests/test_dashboard_jobs.py`
- `backend/tests/test_database_integrity_fixes.py`
- `backend/tests/test_e2e_api.py`
- `backend/tests/test_engine_bounds.py`
- `backend/tests/test_extreme_decode_contract.py`
- `backend/tests/test_extreme_enrichers.py`
- `backend/tests/test_extreme_output.py`
- `backend/tests/test_job_dedup.py`
- `backend/tests/test_job_manager.py`
- `backend/tests/test_llm_utils.py`
- `backend/tests/test_model_names.py`
- `backend/tests/test_nightly_pipeline.py`
- `backend/tests/test_nl_screener_exhaustive.py`
- `backend/tests/test_nl_screener_fix.py`
- `backend/tests/test_outcome_tracker.py`
- `backend/tests/test_prediction_logging.py`
- `backend/tests/test_predictions_performance.py`
- `backend/tests/test_quant_engine.py`
- `backend/tests/test_stress_test_engine.py`
- `backend/tests/test_stress_test_jobs.py`
- `backend/tests/test_worker.py`
- `ml-engine/tests/test_alpha158_pipeline.py`

## Verification Matrix

| Change type | Minimum verification | Remote requirement |
|---|---|---|
| Documentation only | `git diff --check -- docs` and source spot-checks. | Not required unless backend code also changed. |
| Router/API change | Route extraction, relevant API tests, live endpoint smoke. | Required for backend tests and health checks. |
| ORM/migration change | Alembic autogenerate/review, `alembic check`, database integrity tests. | Required. |
| Analysis pipeline change | LLM integrity tests, analysis job lifecycle tests, live `/analyze` poll. | Required; beware credit cost. |
| Swift-only UI change | Source review for Theme/haptics/geometry rules. | Do not run xcodebuild. Manual app validation by user. |
| Scheduler/background change | Scheduler config tests, logs, remote service restart, inspect duplicate jobs. | Required. |

## Testing Failure Modes

- Local backend tests can diverge from server env and violate AGENTS.md.
- Route tests may pass while Swift call sites still use stale paths; verify both decorator inventory and URL call sites.
- Database tests can pass on SQLite but fail on PostgreSQL-specific constraints/pooling.
- LLM tests must distinguish deterministic normalization failures from live provider/key failures.
- Generated logs under `backend/tests/backend_integrity_tests/logs/` should not be accidentally treated as source changes unless explicitly required.

## Source-Verified Test and Documentation Drift

- `backend/tests/TEST_INVENTORY.md` reports endpoint-test coverage and known xfail/bug areas; use it as an inventory aid, not as proof current tests pass.
- `backend/pytest.ini` currently has minimal marker configuration (`timeout`).
- README and older research docs still mention local pytest commands. Under current AGENTS.md, those are historical or human-run instructions, not permitted agent workflow.
- Remote integrity script exists at `backend/tests/run_integrity_tests.sh`; run it only through non-interactive SSH on the configured remote host.
- iOS XCTest/UI test files exist, but this agent must not compile or run them with `xcodebuild`.
