# File Inventory Report

**Total files:** 1469
**Generated:** 2026-06-18
**Test legend:** YES = matching test found, NO = untested, N/A = not applicable

## Backend — Routers (API Controllers)

| File | Purpose | Tests | Risk | Status |
|------|---------|-------|------|--------|
| `./backend/routers/__init__.py` | API:   init   | YES | CRITICAL | tested |
| `./backend/routers/alerts.py` | API: alerts | YES | CRITICAL | tested |
| `./backend/routers/analysis.py` | API: analysis | YES | CRITICAL | tested |
| `./backend/routers/anomalies.py` | API: anomalies | NO | CRITICAL | untested |
| `./backend/routers/auth.py` | API: auth | NO | CRITICAL | untested |
| `./backend/routers/brainstorming.py` | API: brainstorming | NO | CRITICAL | untested |
| `./backend/routers/copilot.py` | API: copilot | NO | CRITICAL | untested |
| `./backend/routers/correlation.py` | API: correlation | NO | CRITICAL | untested |
| `./backend/routers/dashboard.py` | API: dashboard | YES | CRITICAL | tested |
| `./backend/routers/earnings_surprise.py` | API: earnings surprise | NO | CRITICAL | untested |
| `./backend/routers/harvester.py` | API: harvester | YES | CRITICAL | tested |
| `./backend/routers/health.py` | API: health | YES | CRITICAL | tested |
| `./backend/routers/market.py` | API: market | YES | CRITICAL | tested |
| `./backend/routers/nl_screener.py` | API: nl screener | YES | CRITICAL | tested |
| `./backend/routers/notifications.py` | API: notifications | NO | CRITICAL | untested |
| `./backend/routers/options_strategy.py` | API: options strategy | NO | CRITICAL | untested |
| `./backend/routers/portfolio.py` | API: portfolio | YES | CRITICAL | tested |
| `./backend/routers/sector_rotation.py` | API: sector rotation | NO | CRITICAL | untested |
| `./backend/routers/strategy.py` | API: strategy | NO | CRITICAL | untested |
| `./backend/routers/stress_test.py` | API: stress test | YES | CRITICAL | tested |
| `./backend/routers/user.py` | API: user | NO | CRITICAL | untested |
## Backend — Services → Math Engines

| File | Purpose | Tests | Risk | Status |
|------|---------|-------|------|--------|
| `./backend/services/math_engines/__init__.py` | Math:   init   | YES | HIGH | tested |
| `./backend/services/math_engines/auditor_risk.py` | Math: auditor risk | NO | HIGH | untested |
| `./backend/services/math_engines/concentration.py` | Math: concentration | NO | HIGH | untested |
| `./backend/services/math_engines/conformal_prediction.py` | Math: conformal prediction | NO | HIGH | untested |
| `./backend/services/math_engines/covariance.py` | Math: covariance | NO | HIGH | untested |
| `./backend/services/math_engines/deterministic_dcf.py` | Math: deterministic dcf | NO | HIGH | untested |
| `./backend/services/math_engines/dtw_pattern_matching.py` | Math: dtw pattern matching | NO | HIGH | untested |
| `./backend/services/math_engines/eps_drift_model.py` | Math: eps drift model | NO | HIGH | untested |
| `./backend/services/math_engines/euclidean_analogues.py` | Math: euclidean analogues | NO | HIGH | untested |
| `./backend/services/math_engines/finbert_sentiment.py` | Math: finbert sentiment | NO | HIGH | untested |
| `./backend/services/math_engines/liquidity.py` | Math: liquidity | NO | HIGH | untested |
| `./backend/services/math_engines/minsky_risk.py` | Math: minsky risk | NO | HIGH | untested |
| `./backend/services/math_engines/momentum_divergence.py` | Math: momentum divergence | NO | HIGH | untested |
| `./backend/services/math_engines/pcr_gex.py` | Math: pcr gex | NO | HIGH | untested |
| `./backend/services/math_engines/piotroski_beneish.py` | Math: piotroski beneish | NO | HIGH | untested |
| `./backend/services/math_engines/portfolio_correlation.py` | Math: portfolio correlation | NO | HIGH | untested |
| `./backend/services/math_engines/protocol.py` | Math: protocol | NO | HIGH | untested |
| `./backend/services/math_engines/relative_rotation_graph.py` | Math: relative rotation graph | NO | HIGH | untested |
| `./backend/services/math_engines/scoring.py` | Math: scoring | NO | HIGH | untested |
| `./backend/services/math_engines/signal_agreement.py` | Math: signal agreement | NO | HIGH | untested |
| `./backend/services/math_engines/vasicek.py` | Math: vasicek | NO | HIGH | untested |
| `./backend/services/math_engines/volume_isolation_forest.py` | Math: volume isolation forest | NO | HIGH | untested |
## Backend — Services (Business Logic)

| File | Purpose | Tests | Risk | Status |
|------|---------|-------|------|--------|
| `./backend/services/__init__.py` | Service:   init   | YES | HIGH | tested |
| `./backend/services/advisor_harvester.py` | Service: advisor harvester | YES | HIGH | tested |
| `./backend/services/ai_engine_monitor.py` | Service: ai engine monitor | YES | HIGH | tested |
| `./backend/services/anomaly_scanner.py` | Service: anomaly scanner | NO | HIGH | untested |
| `./backend/services/brainstorming.py` | Service: brainstorming | NO | HIGH | untested |
| `./backend/services/cache_service.py` | Service: cache service | NO | HIGH | untested |
| `./backend/services/celery_tasks.py` | Service: celery tasks | NO | HIGH | untested |
| `./backend/services/checkpoints.py` | Service: checkpoints | YES | HIGH | tested |
| `./backend/services/confidence_engine.py` | Service: confidence engine | NO | HIGH | untested |
| `./backend/services/copilot_service.py` | Service: copilot service | NO | HIGH | untested |
| `./backend/services/correlation_engine.py` | Service: correlation engine | NO | HIGH | untested |
| `./backend/services/disk_cache.py` | Service: disk cache | NO | HIGH | untested |
| `./backend/services/earnings_surprise.py` | Service: earnings surprise | NO | HIGH | untested |
| `./backend/services/error_telemetry.py` | Service: error telemetry | NO | HIGH | untested |
| `./backend/services/expert_youtube_harvester.py` | Service: expert youtube harvester | NO | HIGH | untested |
| `./backend/services/extreme_enrichers.py` | Service: extreme enrichers | YES | HIGH | tested |
| `./backend/services/factor_engine.py` | Service: factor engine | NO | HIGH | untested |
| `./backend/services/feedback_injector.py` | Service: feedback injector | NO | HIGH | untested |
| `./backend/services/filings_extractor.py` | Service: filings extractor | NO | HIGH | untested |
| `./backend/services/harvest_worker.py` | Service: harvest worker | NO | HIGH | untested |
| `./backend/services/harvester_db.py` | Service: harvester db | NO | HIGH | untested |
| `./backend/services/harvester_expert.py` | Service: harvester expert | NO | HIGH | untested |
| `./backend/services/harvester_reformatter.py` | Service: harvester reformatter | NO | HIGH | untested |
| `./backend/services/harvester_sebi.py` | Service: harvester sebi | NO | HIGH | untested |
| `./backend/services/job_manager.py` | Service: job manager | YES | HIGH | tested |
| `./backend/services/job_worker.py` | Service: job worker | NO | HIGH | untested |
| `./backend/services/llm_utils.py` | Service: llm utils | YES | HIGH | tested |
| `./backend/services/macro_modifiers.py` | Service: macro modifiers | NO | HIGH | untested |
| `./backend/services/microstructure_engine.py` | Service: microstructure engine | NO | HIGH | untested |
| `./backend/services/news_harvester.py` | Service: news harvester | NO | HIGH | untested |
| `./backend/services/nightly_jobs.py` | Service: nightly jobs | NO | HIGH | untested |
| `./backend/services/nl_screener.py` | Service: nl screener | YES | HIGH | tested |
| `./backend/services/nse_client.py` | Service: nse client | NO | HIGH | untested |
| `./backend/services/nse_data_provider.py` | Service: nse data provider | NO | HIGH | untested |
| `./backend/services/options_engine.py` | Service: options engine | NO | HIGH | untested |
| `./backend/services/options_scraper.py` | Service: options scraper | NO | HIGH | untested |
| `./backend/services/orchestrator.py` | Service: orchestrator | NO | HIGH | untested |
| `./backend/services/piotroski.py` | Service: piotroski | NO | HIGH | untested |
| `./backend/services/pkscreener_runner.py` | Service: pkscreener runner | NO | HIGH | untested |
| `./backend/services/portfolio_snapshot.py` | Service: portfolio snapshot | NO | HIGH | untested |
| `./backend/services/quant_engine.py` | Service: quant engine | YES | HIGH | tested |
| `./backend/services/rag_ingestion.py` | Service: rag ingestion | NO | HIGH | untested |
| `./backend/services/rag_tools.py` | Service: rag tools | NO | HIGH | untested |
| `./backend/services/rate_limiter.py` | Service: rate limiter | NO | CRITICAL | untested |
| `./backend/services/scraper.py` | Service: scraper | NO | HIGH | untested |
| `./backend/services/sector_rotation.py` | Service: sector rotation | NO | HIGH | untested |
| `./backend/services/sentiment_engine.py` | Service: sentiment engine | NO | HIGH | untested |
| `./backend/services/staleness.py` | Service: staleness | NO | HIGH | untested |
| `./backend/services/strategy_engine.py` | Service: strategy engine | NO | HIGH | untested |
| `./backend/services/stress_test.py` | Service: stress test | YES | HIGH | tested |
| `./backend/services/stress_test_jobs.py` | Test | YES | HIGH | tested |
| `./backend/services/ticker_matcher.py` | Service: ticker matcher | NO | HIGH | untested |
| `./backend/services/transcript_engine.py` | Service: transcript engine | NO | HIGH | untested |
| `./backend/services/vector_store.py` | Service: vector store | NO | HIGH | untested |
| `./backend/services/yfinance_client.py` | Service: yfinance client | NO | HIGH | untested |
| `./backend/services/youtube_harvester.py` | Service: youtube harvester | YES | HIGH | tested |
## Backend — ORM Models

| File | Purpose | Tests | Risk | Status |
|------|---------|-------|------|--------|
| `./backend/models/db_models.py` | DB models | NO | CRITICAL | untested |
| `./backend/models/signal_config.py` | DB models | NO | HIGH | untested |
## Backend — Pydantic Schemas

| File | Purpose | Tests | Risk | Status |
|------|---------|-------|------|--------|
| `./backend/schemas/__init__.py` | Pydantic schemas | YES | HIGH | tested |
| `./backend/schemas/auth.py` | Pydantic schemas | NO | CRITICAL | untested |
| `./backend/schemas/market.py` | Pydantic schemas | YES | HIGH | tested |
| `./backend/schemas/portfolio.py` | Pydantic schemas | YES | HIGH | tested |
## Backend — Alembic Migrations

| File | Purpose | Tests | Risk | Status |
|------|---------|-------|------|--------|
| `./backend/migrations/README` | Documentation | N/A | HIGH | N/A |
| `./backend/migrations/env.py` | Alembic migration | YES | HIGH | tested |
| `./backend/migrations/script.py.mako` | Alembic migration | N/A | HIGH | N/A |
| `./backend/migrations/versions/0dc3e605ea33_initial_schema.py` | Alembic migration | NO | HIGH | untested |
| `./backend/migrations/versions/1ad82d60efcc_convert_float_to_numeric_for_precision.py` | Alembic migration | NO | HIGH | untested |
| `./backend/migrations/versions/323c66c5ca0e_auto.py` | Alembic migration | NO | HIGH | untested |
| `./backend/migrations/versions/9929cce0b029_add_stockuniverse_model.py` | Alembic migration | NO | HIGH | untested |
| `./backend/migrations/versions/a1b2c3d4e5f6_add_missing_columns.py` | Alembic migration | NO | HIGH | untested |
| `./backend/migrations/versions/b2c3d4e5f6a7_add_analysis_job_ticker_index.py` | Alembic migration | NO | HIGH | untested |
| `./backend/migrations/versions/d4e5f6a7b8c9_sync_missing_indexes.py` | Alembic migration | NO | HIGH | untested |
## Backend — Repositories (Data Access)

| File | Purpose | Tests | Risk | Status |
|------|---------|-------|------|--------|
| `./backend/repositories/__init__.py` | Data access | YES | HIGH | tested |
| `./backend/repositories/analysis_repo.py` | Data access | NO | HIGH | untested |
| `./backend/repositories/job_repo.py` | Data access | NO | HIGH | untested |
| `./backend/repositories/stress_test_repo.py` | Test | NO | HIGH | untested |
## Backend — Core Infrastructure

| File | Purpose | Tests | Risk | Status |
|------|---------|-------|------|--------|
| `./backend/core/__init__.py` | Core infra | YES | CRITICAL | tested |
| `./backend/core/concurrency.py` | Core infra | YES | CRITICAL | tested |
| `./backend/core/dashboard_state.py` | Core infra | NO | CRITICAL | untested |
| `./backend/core/logging_config.py` | Core infra | NO | CRITICAL | untested |
| `./backend/core/rate_limiter.py` | Core infra | NO | CRITICAL | untested |
| `./backend/core/security.py` | Core infra | NO | CRITICAL | untested |
## Backend — Middleware

| File | Purpose | Tests | Risk | Status |
|------|---------|-------|------|--------|
| `./backend/middleware/__init__.py` | Middleware | YES | HIGH | tested |
| `./backend/middleware/request_log.py` | Middleware | NO | CRITICAL | untested |
| `./backend/middleware/security_headers.py` | Middleware | NO | CRITICAL | untested |
## Backend — Config

| File | Purpose | Tests | Risk | Status |
|------|---------|-------|------|--------|
| `./backend/config/__init__.py` | Config | YES | LOW | tested |
| `./backend/config/prompts_config.py` | Config | NO | HIGH | untested |
| `./backend/config/settings.py` | Config | NO | CRITICAL | untested |
| `./backend/config/signal_config.json` | Config | N/A | HIGH | N/A |
## Backend — Data Files

| File | Purpose | Tests | Risk | Status |
|------|---------|-------|------|--------|
| `./backend/data/nse_bse_symbols.json` | JSON/config | N/A | LOW | N/A |
## Backend — Root (Critical Modules)

| File | Purpose | Tests | Risk | Status |
|------|---------|-------|------|--------|
| `./backend/.env` |  file | N/A | CRITICAL | N/A |
| `./backend/.env.example` | .example file | N/A | CRITICAL | N/A |
| `./backend/.fuse_hidden0000000e00000001` |  file | N/A | LOW | N/A |
| `./backend/.fuse_hidden0000000e00000002` |  file | N/A | LOW | N/A |
| `./backend/.fuse_hidden0000000e00000003` |  file | N/A | LOW | N/A |
| `./backend/.gitignore` | Git/cache metadata | N/A | LOW | N/A |
| `./backend/AGENT_MAP.md` | Documentation | N/A | LOW | N/A |
| `./backend/Dockerfile` | Docker container definition | N/A | LOW | N/A |
| `./backend/Indian Market AI Analysis Framework.txt` | Text | N/A | LOW | N/A |
| `./backend/Indian Market Behavioral Prompt Engineering.txt` | Text | N/A | LOW | N/A |
| `./backend/Indian Stock App Feature Analysis.txt` | Text | N/A | LOW | N/A |
| `./backend/Indian Stock App Feature Discovery.md` | Documentation | N/A | LOW | N/A |
| `./backend/Indian_Equity_Stress_Test_Engine.md` | Test | N/A | LOW | N/A |
| `./backend/alembic.ini` | .ini file | N/A | LOW | N/A |
| `./backend/bugs.md` | Documentation | N/A | LOW | N/A |
| `./backend/changes.md` | Documentation | N/A | LOW | N/A |
| `./backend/comprehensive_tests_explanation.md` | Documentation | N/A | LOW | N/A |
| `./backend/database.py` | Python module | YES | CRITICAL | tested |
| `./backend/debug_harvester_sources.py` | Python module | NO | HIGH | untested |
| `./backend/deploy_update.sh` | Shell script | N/A | LOW | N/A |
| `./backend/harvester.db` | SQLite DB | N/A | LOW | N/A |
| `./backend/helpers.py` | Python module | NO | HIGH | untested |
| `./backend/main.py` | Python module | NO | CRITICAL | untested |
| `./backend/nivesh.db` | SQLite DB | N/A | LOW | N/A |
| `./backend/nivesh.service` | .service file | N/A | LOW | N/A |
| `./backend/nivesh_app_context.md` | Documentation | N/A | LOW | N/A |
| `./backend/populate_portfolio.py` | Python module | NO | HIGH | untested |
| `./backend/portfolio_charts.py` | Python module | NO | HIGH | untested |
| `./backend/prompts.py` | Python module | NO | HIGH | untested |
| `./backend/pytest.ini` | .ini file | N/A | LOW | N/A |
| `./backend/requirements.txt` | Python dependencies | N/A | LOW | N/A |
| `./backend/run.sh` | Shell script | N/A | LOW | N/A |
| `./backend/run_advisor_harvest.py` | Python module | NO | HIGH | untested |
| `./backend/schemas.py` | Python module | NO | HIGH | untested |
| `./backend/scratch_dividend.py` | Python module | NO | HIGH | untested |
| `./backend/scratch_item38.py` | Python module | NO | HIGH | untested |
| `./backend/scratch_item38_router.py` | Python module | NO | HIGH | untested |
| `./backend/scratch_item39.py` | Python module | NO | HIGH | untested |
| `./backend/scratch_item49.py` | Python module | NO | HIGH | untested |
| `./backend/scratch_middleware.py` | Python module | NO | HIGH | untested |
| `./backend/scratch_yf_test.py` | Python module | NO | HIGH | untested |
| `./backend/stockapp.db` | SQLite DB | N/A | LOW | N/A |
| `./backend/stockapp_test.db` | SQLite DB | N/A | LOW | N/A |
| `./backend/tasks_advisor.md` | Documentation | N/A | LOW | N/A |
| `./backend/tasks_api_key_deployment.md` | Documentation | N/A | LOW | N/A |
| `./backend/tasks_ensemble.md` | Documentation | N/A | LOW | N/A |
| `./backend/tasks_final_refactor.md` | Documentation | N/A | LOW | N/A |
| `./backend/telemetry_spec.json` | JSON/config | N/A | LOW | N/A |
| `./backend/test_analyze_diagnostic.py` | Test | NO | HIGH | untested |
| `./backend/test_analyze_uncached.py` | Test | NO | HIGH | untested |
| `./backend/test_cache.py` | Test | YES | HIGH | tested |
| `./backend/test_claude.py` | Test | NO | HIGH | untested |
| `./backend/test_deep_scan.py` | Test | NO | HIGH | untested |
| `./backend/test_deepseek_claude.py` | Test | NO | HIGH | untested |
| `./backend/test_new_endpoints.py` | Test | NO | HIGH | untested |
| `./backend/test_nse.py` | Test | NO | HIGH | untested |
| `./backend/test_run.py` | Test | NO | HIGH | untested |
| `./backend/test_watchlist.py` | Test | NO | HIGH | untested |
| `./backend/test_watchlist_db.py` | Test | NO | HIGH | untested |
| `./backend/test_yf_history.py` | Test | NO | HIGH | untested |
| `./backend/test_yf_info.py` | Test | NO | HIGH | untested |
| `./backend/token_log.jsonl` | .jsonl file | N/A | LOW | N/A |
| `./backend/update.sh` | Shell script | N/A | LOW | N/A |
## Backend — Scripts

| File | Purpose | Tests | Risk | Status |
|------|---------|-------|------|--------|
| `./backend/scripts/cache_cleanup.sh` | Utility script | N/A | MEDIUM | N/A |
| `./backend/scripts/check_backend_health.sh` | Utility script | N/A | MEDIUM | N/A |
| `./backend/scripts/check_jobs.py` | Utility script | NO | MEDIUM | untested |
| `./backend/scripts/check_stress_test_status.py` | Test | NO | MEDIUM | untested |
| `./backend/scripts/generate_improvement_prompts.py` | Utility script | NO | MEDIUM | untested |
| `./backend/scripts/migrate_fix_fk_orphans.py` | Utility script | NO | MEDIUM | untested |
| `./backend/scripts/monitor_model_drift.py` | Utility script | NO | MEDIUM | untested |
| `./backend/scripts/populate_stock_universe.py` | Utility script | NO | MEDIUM | untested |
| `./backend/scripts/refresh_nse_symbols.py` | Utility script | NO | MEDIUM | untested |
| `./backend/scripts/reset_mock_user.py` | Utility script | NO | MEDIUM | untested |
| `./backend/scripts/show_result.py` | Utility script | NO | MEDIUM | untested |
| `./backend/scripts/smoke_all_endpoints.py` | Utility script | NO | MEDIUM | untested |
| `./backend/scripts/test_quant.py` | Test | YES | MEDIUM | tested |
| `./backend/scripts/validate_openapi.py` | Utility script | NO | MEDIUM | untested |
| `./backend/scripts/verify_model_migration_drift.py` | Utility script | NO | MEDIUM | untested |
| `./backend/scripts/verify_raw_sql_columns.py` | Utility script | NO | MEDIUM | untested |
| `./backend/scripts/verify_route_registration.py` | Utility script | NO | MEDIUM | untested |
| `./backend/tradingagents-core/scripts/smoke_structured_output.py` | Utility script | NO | MEDIUM | untested |
## Backend — Tests → Backend_Integrity

| File | Purpose | Tests | Risk | Status |
|------|---------|-------|------|--------|
| `./backend/tests/backend_integrity_tests/__init__.py` | Python module | N/A | MEDIUM | N/A |
| `./backend/tests/backend_integrity_tests/_base.py` | Python module | N/A | MEDIUM | N/A |
| `./backend/tests/backend_integrity_tests/run_all.py` | Python module | N/A | MEDIUM | N/A |
| `./backend/tests/backend_integrity_tests/test_01_imports_circular.py` | Test | N/A | MEDIUM | N/A |
| `./backend/tests/backend_integrity_tests/test_02_syntax_lint.py` | Test | N/A | MEDIUM | N/A |
| `./backend/tests/backend_integrity_tests/test_03_exception_catalog.py` | Test | N/A | MEDIUM | N/A |
| `./backend/tests/backend_integrity_tests/test_04_sqlalchemy_exceptions.py` | Test | N/A | MEDIUM | N/A |
| `./backend/tests/backend_integrity_tests/test_05_fastapi_exceptions.py` | Test | N/A | MEDIUM | N/A |
| `./backend/tests/backend_integrity_tests/test_06_python_builtins_exceptions.py` | Test | N/A | MEDIUM | N/A |
| `./backend/tests/backend_integrity_tests/test_07_os_io_exceptions.py` | Test | N/A | MEDIUM | N/A |
| `./backend/tests/backend_integrity_tests/test_08_unicode_exceptions.py` | Test | N/A | MEDIUM | N/A |
| `./backend/tests/backend_integrity_tests/test_09_runtime_exceptions.py` | Test | N/A | MEDIUM | N/A |
| `./backend/tests/backend_integrity_tests/test_10_warning_catalog.py` | Test | N/A | MEDIUM | N/A |
## Backend — Tests → Database_Integrity

| File | Purpose | Tests | Risk | Status |
|------|---------|-------|------|--------|
| `./backend/tests/database_integrity_tests/__init__.py` | Python module | N/A | MEDIUM | N/A |
| `./backend/tests/database_integrity_tests/_base.py` | Python module | N/A | MEDIUM | N/A |
| `./backend/tests/database_integrity_tests/run_all.py` | Python module | N/A | MEDIUM | N/A |
| `./backend/tests/database_integrity_tests/test_01_schema_columns.py` | Test | N/A | MEDIUM | N/A |
| `./backend/tests/database_integrity_tests/test_02_constraints.py` | Test | N/A | MEDIUM | N/A |
| `./backend/tests/database_integrity_tests/test_03_relationships.py` | Test | N/A | MEDIUM | N/A |
| `./backend/tests/database_integrity_tests/test_04_migration_drift.py` | Test | N/A | MEDIUM | N/A |
| `./backend/tests/database_integrity_tests/test_05_crud_lifecycle.py` | Test | N/A | MEDIUM | N/A |
| `./backend/tests/database_integrity_tests/test_06_session_management.py` | Test | N/A | MEDIUM | N/A |
| `./backend/tests/database_integrity_tests/test_07_concurrent_writes.py` | Test | N/A | MEDIUM | N/A |
| `./backend/tests/database_integrity_tests/test_08_null_enforcement.py` | Test | N/A | MEDIUM | N/A |
| `./backend/tests/database_integrity_tests/test_09_foreign_keys.py` | Test | N/A | MEDIUM | N/A |
| `./backend/tests/database_integrity_tests/test_10_unique_constraints.py` | Test | N/A | MEDIUM | N/A |
| `./backend/tests/database_integrity_tests/test_11_check_constraints.py` | Test | N/A | MEDIUM | N/A |
| `./backend/tests/database_integrity_tests/test_12_indexes.py` | Test | N/A | MEDIUM | N/A |
| `./backend/tests/database_integrity_tests/test_13_telemetry_tables.py` | Test | N/A | MEDIUM | N/A |
| `./backend/tests/database_integrity_tests/test_14_seed_data.py` | Test | N/A | MEDIUM | N/A |
| `./backend/tests/database_integrity_tests/test_15_error_recovery.py` | Test | N/A | MEDIUM | N/A |
## Backend — Tests → Cache_Integrity

| File | Purpose | Tests | Risk | Status |
|------|---------|-------|------|--------|
| `./backend/tests/cache_integrity_tests/_base.py` | Python module | N/A | MEDIUM | N/A |
| `./backend/tests/cache_integrity_tests/run_all.py` | Python module | N/A | MEDIUM | N/A |
| `./backend/tests/cache_integrity_tests/test_01_cache_gates.py` | Test | N/A | MEDIUM | N/A |
| `./backend/tests/cache_integrity_tests/test_02_concurrency_dedup.py` | Test | N/A | MEDIUM | N/A |
## Backend — Tests → Llm_Integrity

| File | Purpose | Tests | Risk | Status |
|------|---------|-------|------|--------|
| `./backend/tests/llm_integrity_tests/_base.py` | Python module | N/A | MEDIUM | N/A |
| `./backend/tests/llm_integrity_tests/run_all.py` | Python module | N/A | MEDIUM | N/A |
| `./backend/tests/llm_integrity_tests/test_01_json_normalization.py` | Test | N/A | MEDIUM | N/A |
| `./backend/tests/llm_integrity_tests/test_02_indian_formatting.py` | Test | N/A | MEDIUM | N/A |
| `./backend/tests/llm_integrity_tests/test_03_prompt_integrity.py` | Test | N/A | MEDIUM | N/A |
## Backend — Tests → Feature

| File | Purpose | Tests | Risk | Status |
|------|---------|-------|------|--------|
| `./backend/tests/feature_tests/advisor_harvester/test_advisor_harvester.py` | Test | N/A | MEDIUM | N/A |
| `./backend/tests/feature_tests/alerts/test_alerts.py` | Test | N/A | MEDIUM | N/A |
| `./backend/tests/feature_tests/analysis_engine/test_analysis_engine.py` | Test | N/A | MEDIUM | N/A |
| `./backend/tests/feature_tests/earnings_dashboard/test_earnings_dashboard.py` | Test | N/A | MEDIUM | N/A |
| `./backend/tests/feature_tests/macro_impact/test_macro_impact.py` | Test | N/A | MEDIUM | N/A |
| `./backend/tests/feature_tests/news_feed/test_news_feed.py` | Test | N/A | MEDIUM | N/A |
| `./backend/tests/feature_tests/portfolio_calendar/test_portfolio_calendar.py` | Test | N/A | MEDIUM | N/A |
| `./backend/tests/feature_tests/screener/test_screener.py` | Test | N/A | MEDIUM | N/A |
| `./backend/tests/feature_tests/sector_performance/test_sector_performance.py` | Test | N/A | MEDIUM | N/A |
| `./backend/tests/feature_tests/tech_momentum/test_tech_momentum.py` | Test | N/A | MEDIUM | N/A |
| `./backend/tests/feature_tests/youtube_harvester/test_youtube_harvester.py` | Test | N/A | MEDIUM | N/A |
## Backend — Tests → Morning_Briefing

| File | Purpose | Tests | Risk | Status |
|------|---------|-------|------|--------|
| `./backend/tests/morning_briefing/__init__.py` | Python module | N/A | MEDIUM | N/A |
| `./backend/tests/morning_briefing/conftest.py` | Test fixtures/config | N/A | MEDIUM | N/A |
| `./backend/tests/morning_briefing/test_cache.py` | Test | N/A | MEDIUM | N/A |
| `./backend/tests/morning_briefing/test_concurrency.py` | Test | N/A | CRITICAL | N/A |
| `./backend/tests/morning_briefing/test_edge_cases.py` | Test | N/A | MEDIUM | N/A |
| `./backend/tests/morning_briefing/test_endpoint.py` | Test | N/A | MEDIUM | N/A |
| `./backend/tests/morning_briefing/test_regression.py` | Test | N/A | MEDIUM | N/A |
| `./backend/tests/morning_briefing/test_scheduler.py` | Test | N/A | MEDIUM | N/A |
## Backend — Tests → Migrations

| File | Purpose | Tests | Risk | Status |
|------|---------|-------|------|--------|
| `./backend/tests/migrations/__init__.py` | Python module | N/A | MEDIUM | N/A |
| `./backend/tests/migrations/test_alembic_health.py` | Test | N/A | MEDIUM | N/A |
## Backend — Tests → Api

| File | Purpose | Tests | Risk | Status |
|------|---------|-------|------|--------|
| `./backend/tests/api/__init__.py` | Python module | N/A | MEDIUM | N/A |
| `./backend/tests/api/test_endpoint_contracts.py` | Test | N/A | MEDIUM | N/A |
## Backend — Tests → Db

| File | Purpose | Tests | Risk | Status |
|------|---------|-------|------|--------|
| `./backend/tests/db/__init__.py` | Python module | N/A | MEDIUM | N/A |
| `./backend/tests/db/test_model_integrity.py` | Test | N/A | MEDIUM | N/A |
## Backend — Tests → Smoke

| File | Purpose | Tests | Risk | Status |
|------|---------|-------|------|--------|
| `./backend/tests/smoke/__init__.py` | Python module | N/A | MEDIUM | N/A |
| `./backend/tests/smoke/test_app_startup.py` | Test | N/A | MEDIUM | N/A |
## Backend — Tests → Fixtures

| File | Purpose | Tests | Risk | Status |
|------|---------|-------|------|--------|
| `./backend/tests/fixtures/extreme_reliance.json` | JSON/config | N/A | MEDIUM | N/A |
| `./backend/tests/fixtures/nl_screener/error_parser_failure.json` | JSON/config | N/A | MEDIUM | N/A |
| `./backend/tests/fixtures/nl_screener/error_unsupported_query.json` | JSON/config | N/A | MEDIUM | N/A |
| `./backend/tests/fixtures/nl_screener/malformed_old_response.json` | JSON/config | N/A | MEDIUM | N/A |
| `./backend/tests/fixtures/nl_screener/success_basic.json` | JSON/config | N/A | MEDIUM | N/A |
| `./backend/tests/fixtures/nl_screener/success_empty.json` | JSON/config | N/A | MEDIUM | N/A |
| `./backend/tests/fixtures/nl_screener/success_with_nulls.json` | JSON/config | N/A | MEDIUM | N/A |
## Backend — Tests (Root)

| File | Purpose | Tests | Risk | Status |
|------|---------|-------|------|--------|
| `./backend/tests/TEST_INVENTORY.md` | Test | N/A | MEDIUM | N/A |
| `./backend/tests/conftest.py` | Test fixtures/config | N/A | MEDIUM | N/A |
| `./backend/tests/nivesh_api.postman_collection.json` | JSON/config | N/A | MEDIUM | N/A |
| `./backend/tests/nivesh_local.postman_environment.json` | JSON/config | N/A | MEDIUM | N/A |
| `./backend/tests/nivesh_prod.postman_environment.json` | JSON/config | N/A | MEDIUM | N/A |
| `./backend/tests/run_integrity_tests.sh` | Shell script | N/A | MEDIUM | N/A |
| `./backend/tests/test_ai_engine_monitor.py` | Test | N/A | MEDIUM | N/A |
| `./backend/tests/test_analysis_job.py` | Test | N/A | MEDIUM | N/A |
| `./backend/tests/test_analysis_pipeline_regressions.py` | Test | N/A | MEDIUM | N/A |
| `./backend/tests/test_analyze_api.py` | Test | N/A | MEDIUM | N/A |
| `./backend/tests/test_analyze_dedup_endpoint.py` | Test | N/A | MEDIUM | N/A |
| `./backend/tests/test_backend_contract_api.py` | Test | N/A | MEDIUM | N/A |
| `./backend/tests/test_backend_contract_concurrency.py` | Test | N/A | CRITICAL | N/A |
| `./backend/tests/test_backend_contract_database.py` | Test | N/A | CRITICAL | N/A |
| `./backend/tests/test_backend_contract_db_integrity.py` | Test | N/A | MEDIUM | N/A |
| `./backend/tests/test_backend_contract_financial.py` | Test | N/A | MEDIUM | N/A |
| `./backend/tests/test_backend_contract_migration_metadata.py` | Test | N/A | MEDIUM | N/A |
| `./backend/tests/test_backend_contract_migrations.py` | Test | N/A | MEDIUM | N/A |
| `./backend/tests/test_backend_contract_routes.py` | Test | N/A | MEDIUM | N/A |
| `./backend/tests/test_backend_tasks.py` | Test | N/A | MEDIUM | N/A |
| `./backend/tests/test_calibration_engine.py` | Test | N/A | MEDIUM | N/A |
| `./backend/tests/test_checkpoints.py` | Test | N/A | MEDIUM | N/A |
| `./backend/tests/test_comprehensive.py` | Test | N/A | MEDIUM | N/A |
| `./backend/tests/test_dashboard_jobs.py` | Test | N/A | MEDIUM | N/A |
| `./backend/tests/test_database_integrity_fixes.py` | Test | N/A | MEDIUM | N/A |
| `./backend/tests/test_e2e_api.py` | Test | N/A | MEDIUM | N/A |
| `./backend/tests/test_engine_bounds.py` | Test | N/A | MEDIUM | N/A |
| `./backend/tests/test_extreme_decode_contract.py` | Test | N/A | MEDIUM | N/A |
| `./backend/tests/test_extreme_enrichers.py` | Test | N/A | MEDIUM | N/A |
| `./backend/tests/test_extreme_output.py` | Test | N/A | MEDIUM | N/A |
| `./backend/tests/test_job_dedup.py` | Test | N/A | MEDIUM | N/A |
| `./backend/tests/test_job_manager.py` | Test | N/A | MEDIUM | N/A |
| `./backend/tests/test_llm_utils.py` | Test | N/A | MEDIUM | N/A |
| `./backend/tests/test_model_names.py` | Test | N/A | MEDIUM | N/A |
| `./backend/tests/test_nl_screener_exhaustive.py` | Test | N/A | MEDIUM | N/A |
| `./backend/tests/test_nl_screener_fix.py` | Test | N/A | MEDIUM | N/A |
| `./backend/tests/test_quant_engine.py` | Test | N/A | MEDIUM | N/A |
| `./backend/tests/test_stress_test_engine.py` | Test | N/A | MEDIUM | N/A |
| `./backend/tests/test_stress_test_jobs.py` | Test | N/A | MEDIUM | N/A |
| `./backend/tests/test_worker.py` | Test | N/A | MEDIUM | N/A |
| `./backend/tests_suite/conftest.py` | Test fixtures/config | N/A | MEDIUM | N/A |
| `./backend/tests_suite/test_ai_mock_comprehensive.py` | Test | N/A | MEDIUM | N/A |
| `./backend/tests_suite/test_api_endpoints_comprehensive.py` | Test | N/A | MEDIUM | N/A |
| `./backend/tests_suite/test_database_comprehensive.py` | Test | N/A | MEDIUM | N/A |
| `./backend/tests_suite/test_scraper_mock_comprehensive.py` | Test | N/A | MEDIUM | N/A |
| `./backend/tests_suite/test_staleness_comprehensive.py` | Test | N/A | MEDIUM | N/A |
| `./backend/tests_suite/test_ticker_matcher_comprehensive.py` | Test | N/A | MEDIUM | N/A |
| `./backend/tradingagents-core/tests/__init__.py` | Python module | N/A | MEDIUM | N/A |
| `./backend/tradingagents-core/tests/conftest.py` | Test fixtures/config | N/A | MEDIUM | N/A |
| `./backend/tradingagents-core/tests/test_analyst_execution.py` | Test | N/A | MEDIUM | N/A |
| `./backend/tradingagents-core/tests/test_anthropic_effort.py` | Test | N/A | MEDIUM | N/A |
| `./backend/tradingagents-core/tests/test_api_key_env.py` | Test | N/A | MEDIUM | N/A |
| `./backend/tradingagents-core/tests/test_capabilities.py` | Test | N/A | MEDIUM | N/A |
| `./backend/tradingagents-core/tests/test_checkpoint_resume.py` | Test | N/A | MEDIUM | N/A |
| `./backend/tradingagents-core/tests/test_crypto_asset_mode.py` | Test | N/A | MEDIUM | N/A |
| `./backend/tradingagents-core/tests/test_dataflows_config.py` | Test | N/A | MEDIUM | N/A |
| `./backend/tradingagents-core/tests/test_deepseek_reasoning.py` | Test | N/A | MEDIUM | N/A |
| `./backend/tradingagents-core/tests/test_env_overrides.py` | Test | N/A | MEDIUM | N/A |
| `./backend/tradingagents-core/tests/test_google_api_key.py` | Test | N/A | MEDIUM | N/A |
| `./backend/tradingagents-core/tests/test_instrument_identity.py` | Test | N/A | MEDIUM | N/A |
| `./backend/tradingagents-core/tests/test_market_data_validator.py` | Test | N/A | MEDIUM | N/A |
| `./backend/tradingagents-core/tests/test_memory_log.py` | Test | N/A | MEDIUM | N/A |
| `./backend/tradingagents-core/tests/test_minimax.py` | Test | N/A | MEDIUM | N/A |
| `./backend/tradingagents-core/tests/test_model_validation.py` | Test | N/A | MEDIUM | N/A |
| `./backend/tradingagents-core/tests/test_ollama_base_url.py` | Test | N/A | MEDIUM | N/A |
| `./backend/tradingagents-core/tests/test_reddit_fallback.py` | Test | N/A | MEDIUM | N/A |
| `./backend/tradingagents-core/tests/test_safe_ticker_component.py` | Test | N/A | MEDIUM | N/A |
| `./backend/tradingagents-core/tests/test_signal_processing.py` | Test | N/A | MEDIUM | N/A |
| `./backend/tradingagents-core/tests/test_stockstats_date_column.py` | Test | N/A | MEDIUM | N/A |
| `./backend/tradingagents-core/tests/test_structured_agents.py` | Test | N/A | MEDIUM | N/A |
| `./backend/tradingagents-core/tests/test_temperature_config.py` | Test | N/A | MEDIUM | N/A |
| `./backend/tradingagents-core/tests/test_ticker_symbol_handling.py` | Test | N/A | MEDIUM | N/A |
## TradingAgents — agents

| File | Purpose | Tests | Risk | Status |
|------|---------|-------|------|--------|
| `./backend/tradingagents-core/tradingagents/agents/__init__.py` | Trading agent | YES | MEDIUM | tested |
| `./backend/tradingagents-core/tradingagents/agents/analysts/fundamentals_analyst.py` | Trading agent | NO | MEDIUM | untested |
| `./backend/tradingagents-core/tradingagents/agents/analysts/governance_analyst.py` | Trading agent | NO | MEDIUM | untested |
| `./backend/tradingagents-core/tradingagents/agents/analysts/market_analyst.py` | Trading agent | NO | MEDIUM | untested |
| `./backend/tradingagents-core/tradingagents/agents/analysts/news_analyst.py` | Trading agent | NO | MEDIUM | untested |
| `./backend/tradingagents-core/tradingagents/agents/analysts/sentiment_analyst.py` | Trading agent | NO | MEDIUM | untested |
| `./backend/tradingagents-core/tradingagents/agents/analysts/social_media_analyst.py` | Trading agent | NO | MEDIUM | untested |
| `./backend/tradingagents-core/tradingagents/agents/managers/portfolio_manager.py` | Trading agent | NO | MEDIUM | untested |
| `./backend/tradingagents-core/tradingagents/agents/managers/research_manager.py` | Trading agent | NO | MEDIUM | untested |
| `./backend/tradingagents-core/tradingagents/agents/researchers/bear_researcher.py` | Trading agent | NO | MEDIUM | untested |
| `./backend/tradingagents-core/tradingagents/agents/researchers/bull_researcher.py` | Trading agent | NO | MEDIUM | untested |
| `./backend/tradingagents-core/tradingagents/agents/risk_mgmt/aggressive_debator.py` | Trading agent | NO | MEDIUM | untested |
| `./backend/tradingagents-core/tradingagents/agents/risk_mgmt/conservative_debator.py` | Trading agent | NO | MEDIUM | untested |
| `./backend/tradingagents-core/tradingagents/agents/risk_mgmt/neutral_debator.py` | Trading agent | NO | MEDIUM | untested |
| `./backend/tradingagents-core/tradingagents/agents/schemas.py` | Trading agent | NO | HIGH | untested |
| `./backend/tradingagents-core/tradingagents/agents/trader/trader.py` | Trading agent | NO | MEDIUM | untested |
| `./backend/tradingagents-core/tradingagents/agents/utils/agent_states.py` | Trading agent | NO | MEDIUM | untested |
| `./backend/tradingagents-core/tradingagents/agents/utils/agent_utils.py` | Trading agent | NO | MEDIUM | untested |
| `./backend/tradingagents-core/tradingagents/agents/utils/core_stock_tools.py` | Trading agent | NO | MEDIUM | untested |
| `./backend/tradingagents-core/tradingagents/agents/utils/fundamental_data_tools.py` | Trading agent | NO | MEDIUM | untested |
| `./backend/tradingagents-core/tradingagents/agents/utils/market_data_validation_tools.py` | Trading agent | NO | MEDIUM | untested |
| `./backend/tradingagents-core/tradingagents/agents/utils/memory.py` | Trading agent | YES | MEDIUM | tested |
| `./backend/tradingagents-core/tradingagents/agents/utils/news_data_tools.py` | Trading agent | NO | MEDIUM | untested |
| `./backend/tradingagents-core/tradingagents/agents/utils/rating.py` | Trading agent | NO | MEDIUM | untested |
| `./backend/tradingagents-core/tradingagents/agents/utils/structured.py` | Trading agent | YES | MEDIUM | tested |
| `./backend/tradingagents-core/tradingagents/agents/utils/technical_indicators_tools.py` | Trading agent | NO | MEDIUM | untested |
## TradingAgents — dataflows

| File | Purpose | Tests | Risk | Status |
|------|---------|-------|------|--------|
| `./backend/tradingagents-core/tradingagents/dataflows/__init__.py` | Data provider | YES | MEDIUM | tested |
| `./backend/tradingagents-core/tradingagents/dataflows/alpha_vantage.py` | Data provider | NO | MEDIUM | untested |
| `./backend/tradingagents-core/tradingagents/dataflows/alpha_vantage_common.py` | Data provider | NO | MEDIUM | untested |
| `./backend/tradingagents-core/tradingagents/dataflows/alpha_vantage_fundamentals.py` | Data provider | NO | MEDIUM | untested |
| `./backend/tradingagents-core/tradingagents/dataflows/alpha_vantage_indicator.py` | Data provider | NO | MEDIUM | untested |
| `./backend/tradingagents-core/tradingagents/dataflows/alpha_vantage_news.py` | Data provider | NO | MEDIUM | untested |
| `./backend/tradingagents-core/tradingagents/dataflows/alpha_vantage_stock.py` | Data provider | NO | MEDIUM | untested |
| `./backend/tradingagents-core/tradingagents/dataflows/config.py` | Data provider | YES | MEDIUM | tested |
| `./backend/tradingagents-core/tradingagents/dataflows/indian_news.py` | Data provider | NO | MEDIUM | untested |
| `./backend/tradingagents-core/tradingagents/dataflows/interface.py` | Data provider | NO | MEDIUM | untested |
| `./backend/tradingagents-core/tradingagents/dataflows/market_data_validator.py` | Data provider | YES | MEDIUM | tested |
| `./backend/tradingagents-core/tradingagents/dataflows/reddit.py` | Data provider | YES | MEDIUM | tested |
| `./backend/tradingagents-core/tradingagents/dataflows/stockstats_utils.py` | Data provider | NO | MEDIUM | untested |
| `./backend/tradingagents-core/tradingagents/dataflows/stocktwits.py` | Data provider | NO | MEDIUM | untested |
| `./backend/tradingagents-core/tradingagents/dataflows/utils.py` | Data provider | YES | MEDIUM | tested |
| `./backend/tradingagents-core/tradingagents/dataflows/y_finance.py` | Data provider | NO | MEDIUM | untested |
| `./backend/tradingagents-core/tradingagents/dataflows/yfinance_news.py` | Data provider | NO | MEDIUM | untested |
## TradingAgents — graph

| File | Purpose | Tests | Risk | Status |
|------|---------|-------|------|--------|
| `./backend/tradingagents-core/tradingagents/graph/__init__.py` | LangGraph | YES | MEDIUM | tested |
| `./backend/tradingagents-core/tradingagents/graph/analyst_execution.py` | LangGraph | YES | MEDIUM | tested |
| `./backend/tradingagents-core/tradingagents/graph/checkpointer.py` | LangGraph | NO | MEDIUM | untested |
| `./backend/tradingagents-core/tradingagents/graph/conditional_logic.py` | LangGraph | NO | MEDIUM | untested |
| `./backend/tradingagents-core/tradingagents/graph/propagation.py` | LangGraph | NO | MEDIUM | untested |
| `./backend/tradingagents-core/tradingagents/graph/reflection.py` | LangGraph | NO | MEDIUM | untested |
| `./backend/tradingagents-core/tradingagents/graph/setup.py` | LangGraph | NO | MEDIUM | untested |
| `./backend/tradingagents-core/tradingagents/graph/signal_processing.py` | LangGraph | YES | MEDIUM | tested |
| `./backend/tradingagents-core/tradingagents/graph/trading_graph.py` | LangGraph | NO | MEDIUM | untested |
## TradingAgents — llm_clients

| File | Purpose | Tests | Risk | Status |
|------|---------|-------|------|--------|
| `./backend/tradingagents-core/tradingagents/llm_clients/TODO.md` | LLM client | N/A | MEDIUM | N/A |
| `./backend/tradingagents-core/tradingagents/llm_clients/__init__.py` | LLM client | YES | MEDIUM | tested |
| `./backend/tradingagents-core/tradingagents/llm_clients/anthropic_client.py` | LLM client | NO | MEDIUM | untested |
| `./backend/tradingagents-core/tradingagents/llm_clients/api_key_env.py` | LLM client | YES | MEDIUM | tested |
| `./backend/tradingagents-core/tradingagents/llm_clients/azure_client.py` | LLM client | NO | MEDIUM | untested |
| `./backend/tradingagents-core/tradingagents/llm_clients/base_client.py` | LLM client | NO | MEDIUM | untested |
| `./backend/tradingagents-core/tradingagents/llm_clients/capabilities.py` | LLM client | YES | MEDIUM | tested |
| `./backend/tradingagents-core/tradingagents/llm_clients/factory.py` | LLM client | NO | MEDIUM | untested |
| `./backend/tradingagents-core/tradingagents/llm_clients/google_client.py` | LLM client | NO | MEDIUM | untested |
| `./backend/tradingagents-core/tradingagents/llm_clients/model_catalog.py` | LLM client | NO | MEDIUM | untested |
| `./backend/tradingagents-core/tradingagents/llm_clients/openai_client.py` | LLM client | NO | MEDIUM | untested |
| `./backend/tradingagents-core/tradingagents/llm_clients/validators.py` | LLM client | NO | MEDIUM | untested |
## TradingAgents — nivesh

| File | Purpose | Tests | Risk | Status |
|------|---------|-------|------|--------|
| `./backend/tradingagents-core/tradingagents/nivesh/__init__.py` | Nivesh integration | YES | MEDIUM | tested |
| `./backend/tradingagents-core/tradingagents/nivesh/context_cache.py` | Nivesh integration | NO | MEDIUM | untested |
| `./backend/tradingagents-core/tradingagents/nivesh/reformatter.py` | Nivesh integration | NO | MEDIUM | untested |
| `./backend/tradingagents-core/tradingagents/nivesh/subprocess_runner.py` | Nivesh integration | NO | MEDIUM | untested |
## TradingAgents — Root

| File | Purpose | Tests | Risk | Status |
|------|---------|-------|------|--------|
| `./backend/tradingagents-core/.dockerignore` |  file | N/A | MEDIUM | N/A |
| `./backend/tradingagents-core/.env.enterprise.example` | .example file | N/A | CRITICAL | N/A |
| `./backend/tradingagents-core/.env.example` | .example file | N/A | CRITICAL | N/A |
| `./backend/tradingagents-core/.gitignore` | Git/cache metadata | N/A | MEDIUM | N/A |
| `./backend/tradingagents-core/CHANGELOG.md` | Documentation | N/A | MEDIUM | N/A |
| `./backend/tradingagents-core/Dockerfile` | Docker container definition | N/A | MEDIUM | N/A |
| `./backend/tradingagents-core/LICENSE` | License | N/A | MEDIUM | N/A |
| `./backend/tradingagents-core/README.md` | Documentation | N/A | MEDIUM | N/A |
| `./backend/tradingagents-core/assets/TauricResearch.png` | Image | N/A | MEDIUM | N/A |
| `./backend/tradingagents-core/assets/analyst.png` | Image | N/A | MEDIUM | N/A |
| `./backend/tradingagents-core/assets/cli/cli_init.png` | Image | N/A | MEDIUM | N/A |
| `./backend/tradingagents-core/assets/cli/cli_news.png` | Image | N/A | MEDIUM | N/A |
| `./backend/tradingagents-core/assets/cli/cli_technical.png` | Image | N/A | MEDIUM | N/A |
| `./backend/tradingagents-core/assets/cli/cli_transaction.png` | Image | N/A | MEDIUM | N/A |
| `./backend/tradingagents-core/assets/researcher.png` | Image | N/A | MEDIUM | N/A |
| `./backend/tradingagents-core/assets/risk.png` | Image | N/A | MEDIUM | N/A |
| `./backend/tradingagents-core/assets/schema.png` | Image | N/A | MEDIUM | N/A |
| `./backend/tradingagents-core/assets/trader.png` | Image | N/A | MEDIUM | N/A |
| `./backend/tradingagents-core/assets/wechat.png` | Image | N/A | MEDIUM | N/A |
| `./backend/tradingagents-core/cli/__init__.py` | Python module | YES | MEDIUM | tested |
| `./backend/tradingagents-core/cli/announcements.py` | Python module | NO | MEDIUM | untested |
| `./backend/tradingagents-core/cli/config.py` | Python module | YES | MEDIUM | tested |
| `./backend/tradingagents-core/cli/main.py` | Python module | NO | CRITICAL | untested |
| `./backend/tradingagents-core/cli/models.py` | Python module | NO | HIGH | untested |
| `./backend/tradingagents-core/cli/static/welcome.txt` | Text | N/A | MEDIUM | N/A |
| `./backend/tradingagents-core/cli/stats_handler.py` | Python module | NO | MEDIUM | untested |
| `./backend/tradingagents-core/cli/utils.py` | Python module | YES | MEDIUM | tested |
| `./backend/tradingagents-core/docker-compose.yml` | YAML config | N/A | MEDIUM | N/A |
| `./backend/tradingagents-core/pyproject.toml` | TOML config | N/A | MEDIUM | N/A |
| `./backend/tradingagents-core/requirements.txt` | Python dependencies | N/A | MEDIUM | N/A |
| `./backend/tradingagents-core/test.py` | Python module | YES | MEDIUM | tested |
| `./backend/tradingagents-core/tradingagents.egg-info/PKG-INFO` |  file | N/A | MEDIUM | N/A |
| `./backend/tradingagents-core/tradingagents.egg-info/SOURCES.txt` | Text | N/A | MEDIUM | N/A |
| `./backend/tradingagents-core/tradingagents.egg-info/dependency_links.txt` | Text | N/A | MEDIUM | N/A |
| `./backend/tradingagents-core/tradingagents.egg-info/entry_points.txt` | Text | N/A | MEDIUM | N/A |
| `./backend/tradingagents-core/tradingagents.egg-info/requires.txt` | Text | N/A | MEDIUM | N/A |
| `./backend/tradingagents-core/tradingagents.egg-info/top_level.txt` | Text | N/A | MEDIUM | N/A |
| `./backend/tradingagents-core/tradingagents/__init__.py` | Python module | YES | MEDIUM | tested |
| `./backend/tradingagents-core/tradingagents/default_config.py` | Python module | NO | MEDIUM | untested |
| `./backend/tradingagents-core/uv.lock` | Lock file | N/A | MEDIUM | N/A |
## Backend — Documentation

| File | Purpose | Tests | Risk | Status |
|------|---------|-------|------|--------|
| `./backend/docs/superpowers/plans/2025-05-18-execution-autonomy-resilience.md` | Documentation | N/A | LOW | N/A |
| `./backend/docs/superpowers/plans/2025-05-18-polish-imports-readability.md` | Documentation | N/A | LOW | N/A |
## Backend — Cache Storage

| File | Purpose | Tests | Risk | Status |
|------|---------|-------|------|--------|
| `./backend/.cache/0b99fc5cdbd11703e35a2edb59d078ae.json` | JSON/config | N/A | LOW | N/A |
| `./backend/.cache/177b7409bb1f0125a7877e4bd3577aa6.json` | JSON/config | N/A | LOW | N/A |
| `./backend/.cache/37f93d0ce5c50f05849361c312614cdf.json` | JSON/config | N/A | LOW | N/A |
| `./backend/.cache/40c7002a4c3b592b71a2a264cf4f7376.json` | JSON/config | N/A | LOW | N/A |
| `./backend/.cache/a58c207faedf923f97f7d3945c40ce45.json` | JSON/config | N/A | LOW | N/A |
## Backend — Pytest Cache

| File | Purpose | Tests | Risk | Status |
|------|---------|-------|------|--------|
| `./backend/.pytest_cache/.gitignore` | Git/cache metadata | N/A | LOW | N/A |
| `./backend/.pytest_cache/CACHEDIR.TAG` | .tag file | N/A | LOW | N/A |
| `./backend/.pytest_cache/README.md` | Documentation | N/A | LOW | N/A |
| `./backend/.pytest_cache/v/cache/lastfailed` |  file | N/A | LOW | N/A |
| `./backend/.pytest_cache/v/cache/nodeids` |  file | N/A | LOW | N/A |
## Backend — Logs

| File | Purpose | Tests | Risk | Status |
|------|---------|-------|------|--------|
| `./backend/logs/advisor_harvest.log` | Log | N/A | LOW | N/A |
| `./backend/logs/advisor_harvester.log` | Log | N/A | LOW | N/A |
## Backend — Claude Settings

| File | Purpose | Tests | Risk | Status |
|------|---------|-------|------|--------|
| `./backend/.claude/settings.local.json` | JSON/config | N/A | LOW | N/A |
## Nivesh Harvester — Harvesters

| File | Purpose | Tests | Risk | Status |
|------|---------|-------|------|--------|
| `./nivesh-harvester/harvesters/__init__.py` | Harvester | YES | MEDIUM | tested |
| `./nivesh-harvester/harvesters/expert_scraper.py` | Harvester | NO | MEDIUM | untested |
| `./nivesh-harvester/harvesters/sebi_filings.py` | Harvester | NO | MEDIUM | untested |
| `./nivesh-harvester/harvesters/youtube_harvester.py` | Harvester | YES | MEDIUM | tested |
## Nivesh Harvester — Root

| File | Purpose | Tests | Risk | Status |
|------|---------|-------|------|--------|
| `./nivesh-harvester/.gitignore` | Git/cache metadata | N/A | MEDIUM | N/A |
| `./nivesh-harvester/main.py` | Harvester | NO | CRITICAL | untested |
| `./nivesh-harvester/models.py` | Harvester | NO | HIGH | untested |
| `./nivesh-harvester/nivesh-harvester.service` | Harvester | N/A | MEDIUM | N/A |
| `./nivesh-harvester/reformatter.py` | Harvester | NO | MEDIUM | untested |
| `./nivesh-harvester/requirements.txt` | Python dependencies | N/A | MEDIUM | N/A |
| `./nivesh-harvester/scheduler.py` | Harvester | YES | MEDIUM | tested |
## iOS — Views → StockProfile Tabs

| File | Purpose | Tests | Risk | Status |
|------|---------|-------|------|--------|
| `./ios/StockApp/stockme/stockme/Views/StockProfile/ChartTabView.swift` | iOS UI | N/A | MEDIUM | N/A |
| `./ios/StockApp/stockme/stockme/Views/StockProfile/FinancialsTabView.swift` | iOS UI | N/A | MEDIUM | N/A |
| `./ios/StockApp/stockme/stockme/Views/StockProfile/GovernanceTabView.swift` | iOS UI | N/A | MEDIUM | N/A |
| `./ios/StockApp/stockme/stockme/Views/StockProfile/HoldersTabView.swift` | iOS UI | N/A | MEDIUM | N/A |
| `./ios/StockApp/stockme/stockme/Views/StockProfile/MacroTabView.swift` | iOS UI | N/A | MEDIUM | N/A |
| `./ios/StockApp/stockme/stockme/Views/StockProfile/NewsTabView.swift` | iOS UI | N/A | MEDIUM | N/A |
| `./ios/StockApp/stockme/stockme/Views/StockProfile/OverviewTabView.swift` | iOS UI | N/A | MEDIUM | N/A |
| `./ios/StockApp/stockme/stockme/Views/StockProfile/SPSharedViews.swift` | iOS UI | N/A | MEDIUM | N/A |
| `./ios/StockApp/stockme/stockme/Views/StockProfile/UpdatesTabView.swift` | iOS UI | N/A | MEDIUM | N/A |
## iOS — Views → Analysis

| File | Purpose | Tests | Risk | Status |
|------|---------|-------|------|--------|
| `./ios/StockApp/stockme/stockme/Views/Analysis/AnalysisCoreSections.swift` | iOS UI | N/A | MEDIUM | N/A |
| `./ios/StockApp/stockme/stockme/Views/Analysis/AnalysisErrorStateView.swift` | iOS UI | N/A | MEDIUM | N/A |
| `./ios/StockApp/stockme/stockme/Views/Analysis/AnalysisExtremeSections.swift` | iOS UI | N/A | MEDIUM | N/A |
| `./ios/StockApp/stockme/stockme/Views/Analysis/AnalysisFullView.swift` | iOS UI | N/A | MEDIUM | N/A |
| `./ios/StockApp/stockme/stockme/Views/Analysis/AnalysisLoadingStateView.swift` | iOS UI | N/A | MEDIUM | N/A |
| `./ios/StockApp/stockme/stockme/Views/Analysis/QuantInspectorSheet.swift` | iOS UI | N/A | MEDIUM | N/A |
| `./ios/StockApp/stockme/stockme/Views/Analysis/QuantitativeDriversCard.swift` | iOS UI | N/A | MEDIUM | N/A |
| `./ios/StockApp/stockme/stockme/Views/Analysis/RegimeWarningBanner.swift` | iOS UI | N/A | MEDIUM | N/A |
## iOS — Views (Screens)

| File | Purpose | Tests | Risk | Status |
|------|---------|-------|------|--------|
| `./ios/StockApp/stockme/stockme/Views/AIHowItWorksView.swift` | iOS UI | N/A | MEDIUM | N/A |
| `./ios/StockApp/stockme/stockme/Views/AdvisoryMatrixCard.swift` | iOS UI | N/A | MEDIUM | N/A |
| `./ios/StockApp/stockme/stockme/Views/AlertsScreen.swift` | iOS UI | N/A | MEDIUM | N/A |
| `./ios/StockApp/stockme/stockme/Views/AnalysisHistoryScreen.swift` | iOS UI | N/A | MEDIUM | N/A |
| `./ios/StockApp/stockme/stockme/Views/AnalysisScreen.swift` | iOS UI | N/A | MEDIUM | N/A |
| `./ios/StockApp/stockme/stockme/Views/BrainstormingView.swift` | iOS UI | N/A | MEDIUM | N/A |
| `./ios/StockApp/stockme/stockme/Views/CompareScreen.swift` | iOS UI | N/A | MEDIUM | N/A |
| `./ios/StockApp/stockme/stockme/Views/CopilotScreen.swift` | iOS UI | N/A | MEDIUM | N/A |
| `./ios/StockApp/stockme/stockme/Views/CorrelationMatrixScreen.swift` | iOS UI | N/A | MEDIUM | N/A |
| `./ios/StockApp/stockme/stockme/Views/CrashLabView.swift` | iOS UI | N/A | MEDIUM | N/A |
| `./ios/StockApp/stockme/stockme/Views/DalalStreetConsensusCard.swift` | iOS UI | N/A | MEDIUM | N/A |
| `./ios/StockApp/stockme/stockme/Views/DisclaimerScreen.swift` | iOS UI | N/A | MEDIUM | N/A |
| `./ios/StockApp/stockme/stockme/Views/EarningsDashboardView.swift` | iOS UI | N/A | MEDIUM | N/A |
| `./ios/StockApp/stockme/stockme/Views/EarningsSurpriseScreen.swift` | iOS UI | N/A | MEDIUM | N/A |
| `./ios/StockApp/stockme/stockme/Views/EngineActivityView.swift` | iOS UI | N/A | MEDIUM | N/A |
| `./ios/StockApp/stockme/stockme/Views/ExpertNetworkView.swift` | iOS UI | N/A | MEDIUM | N/A |
| `./ios/StockApp/stockme/stockme/Views/FeatureHelpViews.swift` | iOS UI | N/A | MEDIUM | N/A |
| `./ios/StockApp/stockme/stockme/Views/GlossaryBrowserView.swift` | iOS UI | N/A | MEDIUM | N/A |
| `./ios/StockApp/stockme/stockme/Views/HistoryScreen.swift` | iOS UI | N/A | MEDIUM | N/A |
| `./ios/StockApp/stockme/stockme/Views/HomeScreen.swift` | iOS UI | N/A | MEDIUM | N/A |
| `./ios/StockApp/stockme/stockme/Views/LaunchScreenView.swift` | iOS UI | N/A | MEDIUM | N/A |
| `./ios/StockApp/stockme/stockme/Views/LoginScreen.swift` | iOS UI | N/A | MEDIUM | N/A |
| `./ios/StockApp/stockme/stockme/Views/MarketAnomalyScreen.swift` | iOS UI | N/A | MEDIUM | N/A |
| `./ios/StockApp/stockme/stockme/Views/NLScreenerScreen.swift` | iOS UI | N/A | MEDIUM | N/A |
| `./ios/StockApp/stockme/stockme/Views/NewsMultimediaView.swift` | iOS UI | N/A | MEDIUM | N/A |
| `./ios/StockApp/stockme/stockme/Views/NiveshNavigationSidebar.swift` | iOS UI | N/A | MEDIUM | N/A |
| `./ios/StockApp/stockme/stockme/Views/OnboardingScreen.swift` | iOS UI | N/A | MEDIUM | N/A |
| `./ios/StockApp/stockme/stockme/Views/OptionsStrategyScreen.swift` | iOS UI | N/A | MEDIUM | N/A |
| `./ios/StockApp/stockme/stockme/Views/PortfolioScreen.swift` | iOS UI | N/A | MEDIUM | N/A |
| `./ios/StockApp/stockme/stockme/Views/PreIPOMarketplaceView.swift` | iOS UI | N/A | MEDIUM | N/A |
| `./ios/StockApp/stockme/stockme/Views/QuietHoursView.swift` | iOS UI | N/A | MEDIUM | N/A |
| `./ios/StockApp/stockme/stockme/Views/ReportManagerView.swift` | iOS UI | N/A | MEDIUM | N/A |
| `./ios/StockApp/stockme/stockme/Views/SearchScreen.swift` | iOS UI | N/A | MEDIUM | N/A |
| `./ios/StockApp/stockme/stockme/Views/SectorBlacklistView.swift` | iOS UI | N/A | MEDIUM | N/A |
| `./ios/StockApp/stockme/stockme/Views/SectorRotationScreen.swift` | iOS UI | N/A | MEDIUM | N/A |
| `./ios/StockApp/stockme/stockme/Views/SettingsScreen.swift` | iOS UI | N/A | MEDIUM | N/A |
| `./ios/StockApp/stockme/stockme/Views/StockActionHubView.swift` | iOS UI | N/A | MEDIUM | N/A |
| `./ios/StockApp/stockme/stockme/Views/StockProfileView.swift` | iOS UI | N/A | MEDIUM | N/A |
| `./ios/StockApp/stockme/stockme/Views/StrategyLabScreen.swift` | iOS UI | N/A | MEDIUM | N/A |
| `./ios/StockApp/stockme/stockme/Views/StressTestScreen.swift` | iOS UI | N/A | MEDIUM | N/A |
| `./ios/StockApp/stockme/stockme/Views/TechnicalMomentumView.swift` | iOS UI | N/A | MEDIUM | N/A |
| `./ios/StockApp/stockme/stockme/Views/TermDefinitionSheet.swift` | iOS UI | N/A | MEDIUM | N/A |
| `./ios/StockApp/stockme/stockme/Views/TradeJournalScreen.swift` | iOS UI | N/A | MEDIUM | N/A |
| `./ios/StockApp/stockme/stockme/Views/TutorialOverlayView.swift` | iOS UI | N/A | MEDIUM | N/A |
| `./ios/StockApp/stockme/stockme/Views/ValuationCalendarView.swift` | iOS UI | N/A | MEDIUM | N/A |
## iOS — Components

| File | Purpose | Tests | Risk | Status |
|------|---------|-------|------|--------|
| `./ios/StockApp/stockme/stockme/Components/AdvisorBioCard.swift` | iOS component | N/A | MEDIUM | N/A |
| `./ios/StockApp/stockme/stockme/Components/BanknoteErrorCanvas.swift` | iOS component | N/A | MEDIUM | N/A |
| `./ios/StockApp/stockme/stockme/Components/DialecticProgressView.swift` | iOS component | N/A | MEDIUM | N/A |
| `./ios/StockApp/stockme/stockme/Components/NewsCardView.swift` | iOS component | N/A | MEDIUM | N/A |
| `./ios/StockApp/stockme/stockme/Components/SharedComponents.swift` | iOS component | N/A | MEDIUM | N/A |
| `./ios/StockApp/stockme/stockme/Components/SharedDarkComponents.swift` | iOS component | N/A | MEDIUM | N/A |
| `./ios/StockApp/stockme/stockme/Components/SignalBadgeView.swift` | iOS component | N/A | MEDIUM | N/A |
| `./ios/StockApp/stockme/stockme/Components/StockTapActionSheetModifier.swift` | iOS component | N/A | MEDIUM | N/A |
| `./ios/StockApp/stockme/stockme/Components/YouTubeCardView.swift` | iOS component | N/A | MEDIUM | N/A |
## iOS — Models

| File | Purpose | Tests | Risk | Status |
|------|---------|-------|------|--------|
| `./ios/StockApp/stockme/stockme/Models/AdvisoryModels.swift` | iOS model | N/A | HIGH | N/A |
| `./ios/StockApp/stockme/stockme/Models/AlertModels.swift` | iOS model | N/A | HIGH | N/A |
| `./ios/StockApp/stockme/stockme/Models/AnalysisModels.swift` | iOS model | N/A | HIGH | N/A |
| `./ios/StockApp/stockme/stockme/Models/Common.swift` | iOS model | N/A | HIGH | N/A |
| `./ios/StockApp/stockme/stockme/Models/MarketModels.swift` | iOS model | N/A | HIGH | N/A |
| `./ios/StockApp/stockme/stockme/Models/OptionsModels.swift` | iOS model | N/A | HIGH | N/A |
| `./ios/StockApp/stockme/stockme/Models/PortfolioModels.swift` | iOS model | N/A | HIGH | N/A |
| `./ios/StockApp/stockme/stockme/Models/UtilityModels.swift` | iOS model | N/A | HIGH | N/A |
| `./ios/StockApp/stockme/stockme/Models/WatchlistModels.swift` | iOS model | N/A | HIGH | N/A |
## iOS — Utilities

| File | Purpose | Tests | Risk | Status |
|------|---------|-------|------|--------|
| `./ios/StockApp/stockme/stockme/Utilities/CrashGuard.swift` | iOS utility | N/A | HIGH | N/A |
| `./ios/StockApp/stockme/stockme/Utilities/CrashInterceptor.swift` | iOS utility | N/A | HIGH | N/A |
| `./ios/StockApp/stockme/stockme/Utilities/CrashLog.swift` | iOS utility | N/A | HIGH | N/A |
| `./ios/StockApp/stockme/stockme/Utilities/ErrorDiagnoser.swift` | iOS utility | N/A | HIGH | N/A |
| `./ios/StockApp/stockme/stockme/Utilities/ExplainableTermModifier.swift` | iOS utility | N/A | HIGH | N/A |
| `./ios/StockApp/stockme/stockme/Utilities/Extensions.swift` | iOS utility | N/A | HIGH | N/A |
| `./ios/StockApp/stockme/stockme/Utilities/FinanceTerms.swift` | iOS utility | N/A | HIGH | N/A |
| `./ios/StockApp/stockme/stockme/Utilities/HapticManager.swift` | iOS utility | N/A | HIGH | N/A |
| `./ios/StockApp/stockme/stockme/Utilities/IndianFormatter.swift` | iOS utility | N/A | HIGH | N/A |
| `./ios/StockApp/stockme/stockme/Utilities/ServerURLPolicy.swift` | iOS utility | N/A | HIGH | N/A |
| `./ios/StockApp/stockme/stockme/Utilities/TermDefinitionOverlay.swift` | iOS utility | N/A | HIGH | N/A |
| `./ios/StockApp/stockme/stockme/Utilities/Theme.swift` | iOS utility | N/A | HIGH | N/A |
| `./ios/StockApp/stockme/stockme/Utilities/ThemeManager.swift` | iOS utility | N/A | HIGH | N/A |
| `./ios/StockApp/stockme/stockme/Utilities/TutorialManager.swift` | iOS utility | N/A | HIGH | N/A |
## iOS — Services (API Layer)

| File | Purpose | Tests | Risk | Status |
|------|---------|-------|------|--------|
| `./ios/StockApp/stockme/stockme/Services/APIClient.swift` | iOS API service | N/A | HIGH | N/A |
| `./ios/StockApp/stockme/stockme/Services/URLSessionAPIClient.swift` | iOS API service | N/A | HIGH | N/A |
## iOS — Charts

| File | Purpose | Tests | Risk | Status |
|------|---------|-------|------|--------|
| `./ios/StockApp/stockme/stockme/Charts/ImmersivePortfolioHeroChart.swift` | iOS chart | N/A | HIGH | N/A |
| `./ios/StockApp/stockme/stockme/Charts/ImmersiveStockHeroChart.swift` | iOS chart | N/A | HIGH | N/A |
| `./ios/StockApp/stockme/stockme/Charts/StockCharts.swift` | iOS chart | N/A | HIGH | N/A |
## iOS — StockApp Root (Legacy)

| File | Purpose | Tests | Risk | Status |
|------|---------|-------|------|--------|
| `./ios/StockApp/AnalysisScreen.swift` | Swift source | N/A | LOW | N/A |
| `./ios/StockApp/Components.swift` | Swift source | N/A | LOW | N/A |
| `./ios/StockApp/ContentView.swift` | Swift source | N/A | HIGH | N/A |
| `./ios/StockApp/Formatters.swift` | Swift source | N/A | LOW | N/A |
| `./ios/StockApp/HomeScreen.swift` | Swift source | N/A | LOW | N/A |
| `./ios/StockApp/Models.swift` | Swift source | N/A | LOW | N/A |
| `./ios/StockApp/NetworkManager.swift` | Swift source | N/A | HIGH | N/A |
| `./ios/StockApp/SearchScreen.swift` | Swift source | N/A | LOW | N/A |
| `./ios/StockApp/StockAppApp.swift` | Swift source | N/A | LOW | N/A |
| `./ios/StockApp/StockDatabase.swift` | Swift source | N/A | HIGH | N/A |
| `./ios/StockApp/WatchlistScreen.swift` | Swift source | N/A | LOW | N/A |
| `./ios/StockApp/WatchlistStore.swift` | Swift source | N/A | LOW | N/A |
| `./ios/StockApp/fix_ui.py` | Python module | NO | LOW | untested |
| `./ios/StockApp/stockme/Info.plist` | Plist | N/A | LOW | N/A |
| `./ios/StockApp/stockme/LaunchScreen.storyboard` | Storyboard | N/A | LOW | N/A |
| `./ios/StockApp/stockme/NiveshWidget/Info.plist` | Plist | N/A | LOW | N/A |
| `./ios/StockApp/stockme/NiveshWidget/NiveshWidget.swift` | Swift source | N/A | LOW | N/A |
| `./ios/StockApp/stockme/add_frameworks.rb` | Ruby script | N/A | LOW | N/A |
| `./ios/StockApp/stockme/add_shared.rb` | Ruby script | N/A | LOW | N/A |
| `./ios/StockApp/stockme/add_target.rb` | Ruby script | N/A | LOW | N/A |
| `./ios/StockApp/stockme/dump.rb` | Ruby script | N/A | LOW | N/A |
| `./ios/StockApp/stockme/fix_files.rb` | Ruby script | N/A | LOW | N/A |
| `./ios/StockApp/stockme/fix_product_name.rb` | Ruby script | N/A | LOW | N/A |
| `./ios/StockApp/stockme/launch_animated.mp4` | Video | N/A | LOW | N/A |
| `./ios/StockApp/stockme/list_files.rb` | Ruby script | N/A | LOW | N/A |
| `./ios/StockApp/stockme/remove_ext.rb` | Ruby script | N/A | LOW | N/A |
| `./ios/StockApp/stockme/remove_haptic.rb` | Ruby script | N/A | LOW | N/A |
| `./ios/StockApp/stockme/stockme/AnalysisEngineManager.swift` | Swift source | N/A | HIGH | N/A |
| `./ios/StockApp/stockme/stockme/AppDelegate.swift` | Swift source | N/A | LOW | N/A |
| `./ios/StockApp/stockme/stockme/AppSoundManager.swift` | Swift source | N/A | LOW | N/A |
| `./ios/StockApp/stockme/stockme/AuthManager.swift` | Swift source | N/A | HIGH | N/A |
| `./ios/StockApp/stockme/stockme/BanknoteDesignSystem.swift` | Swift source | N/A | HIGH | N/A |
| `./ios/StockApp/stockme/stockme/ContentView.swift` | Swift source | N/A | HIGH | N/A |
| `./ios/StockApp/stockme/stockme/DenominationBackground.swift` | Swift source | N/A | LOW | N/A |
| `./ios/StockApp/stockme/stockme/HomeFeedModels.swift` | Swift source | N/A | HIGH | N/A |
| `./ios/StockApp/stockme/stockme/HomeFeedService.swift` | Swift source | N/A | HIGH | N/A |
| `./ios/StockApp/stockme/stockme/HomeFeedViewModel.swift` | Swift source | N/A | HIGH | N/A |
| `./ios/StockApp/stockme/stockme/LaunchSequenceView.swift` | Swift source | N/A | HIGH | N/A |
| `./ios/StockApp/stockme/stockme/Models.swift` | Swift source | N/A | LOW | N/A |
| `./ios/StockApp/stockme/stockme/NetworkManager+Sidebar.swift` | Swift source | N/A | LOW | N/A |
| `./ios/StockApp/stockme/stockme/NetworkManager.swift` | Swift source | N/A | HIGH | N/A |
| `./ios/StockApp/stockme/stockme/NotificationManager.swift` | Swift source | N/A | HIGH | N/A |
| `./ios/StockApp/stockme/stockme/StockDatabase.swift` | Swift source | N/A | HIGH | N/A |
| `./ios/StockApp/stockme/stockme/StockProfileViewModel.swift` | Swift source | N/A | HIGH | N/A |
| `./ios/StockApp/stockme/stockme/ValuationCalendarService.swift` | Swift source | N/A | HIGH | N/A |
| `./ios/StockApp/stockme/stockme/WatchlistScreen.swift` | Swift source | N/A | LOW | N/A |
| `./ios/StockApp/stockme/stockme/nivesh_ios_icon.svg` | Vector | N/A | LOW | N/A |
| `./ios/StockApp/stockme/stockme/stockmeApp.swift` | Swift source | N/A | HIGH | N/A |
## iOS — Root

| File | Purpose | Tests | Risk | Status |
|------|---------|-------|------|--------|
| `./ios/.claude/settings.local.json` | JSON/config | N/A | LOW | N/A |
| `./ios/GEMINI.md` | Documentation | N/A | LOW | N/A |
| `./ios/HOW_THE_ANALYSIS_WORKS.md` | Documentation | N/A | LOW | N/A |
| `./ios/NIVESH_FULL_CONTEXT.md` | Documentation | N/A | LOW | N/A |
| `./ios/backend_nivesh_context.md` | Documentation | N/A | LOW | N/A |
| `./ios/frontend_nivesh_context.md` | Documentation | N/A | LOW | N/A |
| `./ios/generate_frontend_prompts.py` | Python module | NO | LOW | untested |
| `./ios/generate_icons.py` | Python module | NO | LOW | untested |
| `./ios/main_copy.py` | Python module | NO | LOW | untested |
| `./ios/optimized_blocks.py` | Python module | NO | LOW | untested |
| `./ios/scraper_copy.py` | Python module | NO | LOW | untested |
| `./ios/test_yf_news.py` | Test | NO | LOW | untested |
| `./ios/update_main_surgically.py` | Python module | NO | LOW | untested |
| `./ios/update_main_surgically_v2.py` | Python module | NO | LOW | untested |
| `./ios/update_main_surgically_v3.py` | Python module | NO | LOW | untested |
## iOS — Tests

| File | Purpose | Tests | Risk | Status |
|------|---------|-------|------|--------|
| `./ios/StockApp/stockme/stockmeTests/NLScreenerTests.swift` | Swift source | N/A | MEDIUM | N/A |
| `./ios/StockApp/stockme/stockmeTests/stockmeTests.swift` | Swift source | N/A | MEDIUM | N/A |
## iOS — UI Tests

| File | Purpose | Tests | Risk | Status |
|------|---------|-------|------|--------|
| `./ios/StockApp/stockme/stockmeUITests/stockmeUITests.swift` | Swift source | N/A | MEDIUM | N/A |
| `./ios/StockApp/stockme/stockmeUITests/stockmeUITestsLaunchTests.swift` | Swift source | N/A | MEDIUM | N/A |
## iOS — Assets

| File | Purpose | Tests | Risk | Status |
|------|---------|-------|------|--------|
| `./ios/StockApp/stockme/stockme/Assets.xcassets/AccentColor.colorset/Contents.json` | Asset | N/A | LOW | N/A |
| `./ios/StockApp/stockme/stockme/Assets.xcassets/AppIcon.appiconset/Contents.json` | Asset | N/A | LOW | N/A |
| `./ios/StockApp/stockme/stockme/Assets.xcassets/AppIcon.appiconset/Icon-1024.png` | Asset | N/A | LOW | N/A |
| `./ios/StockApp/stockme/stockme/Assets.xcassets/AppIcon.appiconset/Icon-120.png` | Asset | N/A | LOW | N/A |
| `./ios/StockApp/stockme/stockme/Assets.xcassets/AppIcon.appiconset/Icon-152.png` | Asset | N/A | LOW | N/A |
| `./ios/StockApp/stockme/stockme/Assets.xcassets/AppIcon.appiconset/Icon-167.png` | Asset | N/A | LOW | N/A |
| `./ios/StockApp/stockme/stockme/Assets.xcassets/AppIcon.appiconset/Icon-180.png` | Asset | N/A | LOW | N/A |
| `./ios/StockApp/stockme/stockme/Assets.xcassets/AppIcon.appiconset/Icon-20.png` | Asset | N/A | LOW | N/A |
| `./ios/StockApp/stockme/stockme/Assets.xcassets/AppIcon.appiconset/Icon-29.png` | Asset | N/A | LOW | N/A |
| `./ios/StockApp/stockme/stockme/Assets.xcassets/AppIcon.appiconset/Icon-40.png` | Asset | N/A | LOW | N/A |
| `./ios/StockApp/stockme/stockme/Assets.xcassets/AppIcon.appiconset/Icon-58.png` | Asset | N/A | LOW | N/A |
| `./ios/StockApp/stockme/stockme/Assets.xcassets/AppIcon.appiconset/Icon-60.png` | Asset | N/A | LOW | N/A |
| `./ios/StockApp/stockme/stockme/Assets.xcassets/AppIcon.appiconset/Icon-76.png` | Asset | N/A | LOW | N/A |
| `./ios/StockApp/stockme/stockme/Assets.xcassets/AppIcon.appiconset/Icon-80.png` | Asset | N/A | LOW | N/A |
| `./ios/StockApp/stockme/stockme/Assets.xcassets/AppIcon.appiconset/Icon-87.png` | Asset | N/A | LOW | N/A |
| `./ios/StockApp/stockme/stockme/Assets.xcassets/Contents.json` | Asset | N/A | LOW | N/A |
## iOS — Xcode Project

| File | Purpose | Tests | Risk | Status |
|------|---------|-------|------|--------|
| `./ios/StockApp/stockme/stockme.xcodeproj/project.pbxproj` | Xcode project | N/A | LOW | N/A |
| `./ios/StockApp/stockme/stockme.xcodeproj/project.xcworkspace/contents.xcworkspacedata` | Xcode project | N/A | LOW | N/A |
| `./ios/StockApp/stockme/stockme.xcodeproj/project.xcworkspace/xcuserdata/saumya.xcuserdatad/UserInterfaceState.xcuserstate` | Xcode project | N/A | LOW | N/A |
| `./ios/StockApp/stockme/stockme.xcodeproj/xcshareddata/xcschemes/NiveshWidgetExtension.xcscheme` | Xcode project | N/A | LOW | N/A |
| `./ios/StockApp/stockme/stockme.xcodeproj/xcshareddata/xcschemes/stockme.xcscheme` | Xcode project | N/A | LOW | N/A |
| `./ios/StockApp/stockme/stockme.xcodeproj/xcuserdata/saumya.xcuserdatad/xcschemes/xcschememanagement.plist` | Xcode project | N/A | LOW | N/A |
## iOS — Documentation

| File | Purpose | Tests | Risk | Status |
|------|---------|-------|------|--------|
| `./ios/docs/superpowers/plans/2026-06-02-backend-upgrades-and-features-16-19.md` | Documentation | N/A | LOW | N/A |
| `./ios/docs/superpowers/plans/2026-06-02-market-data-and-news-reader.md` | Documentation | N/A | LOW | N/A |
| `./ios/docs/superpowers/specs/2026-06-02-market-data-and-news-reader-design.md` | Documentation | N/A | LOW | N/A |
## Docs — Superpowers Plans & Specs

| File | Purpose | Tests | Risk | Status |
|------|---------|-------|------|--------|
| `./docs/superpowers/plans/2026-06-12-analysis-engine-v2-backend.md` | Documentation | N/A | LOW | N/A |
| `./docs/superpowers/plans/2026-06-12-analysis-engine-v2-ios.md` | Documentation | N/A | LOW | N/A |
| `./docs/superpowers/plans/2026-06-12-extreme-analysis-fix.md` | Documentation | N/A | LOW | N/A |
| `./docs/superpowers/plans/2026-06-13-beginner-friendly-plan.md` | Documentation | N/A | LOW | N/A |
| `./docs/superpowers/plans/2026-06-13-crash-defense-system-plan.md` | Documentation | N/A | LOW | N/A |
| `./docs/superpowers/plans/2026-06-13-stream-a-extreme-dossier-plan.md` | Documentation | N/A | LOW | N/A |
| `./docs/superpowers/plans/2026-06-13-stream-b-morning-brief-card-plan.md` | Documentation | N/A | LOW | N/A |
| `./docs/superpowers/plans/2026-06-13-stream-c-settings-expansion-plan.md` | Documentation | N/A | LOW | N/A |
| `./docs/superpowers/plans/2026-06-14-vector-db-rag-plan.md` | Documentation | N/A | LOW | N/A |
| `./docs/superpowers/plans/2026-06-16-ai-engine-dashboard.md` | Documentation | N/A | LOW | N/A |
| `./docs/superpowers/plans/2026-06-16-backend-test-audit.md` | Documentation | N/A | LOW | N/A |
| `./docs/superpowers/specs/2026-06-12-analysis-engine-v2-design.md` | Documentation | N/A | LOW | N/A |
| `./docs/superpowers/specs/2026-06-12-extreme-analysis-fix-design.md` | Documentation | N/A | LOW | N/A |
| `./docs/superpowers/specs/2026-06-13-beginner-friendly-design.md` | Documentation | N/A | LOW | N/A |
| `./docs/superpowers/specs/2026-06-13-crash-defense-system-design.md` | Documentation | N/A | LOW | N/A |
| `./docs/superpowers/specs/2026-06-13-premium-dossier-morning-brief-settings-design.md` | Documentation | N/A | LOW | N/A |
| `./docs/superpowers/specs/2026-06-14-vector-db-rag-design.md` | Documentation | N/A | LOW | N/A |
| `./docs/superpowers/specs/2026-06-16-ai-engine-dashboard-design.md` | Documentation | N/A | LOW | N/A |
## Investigations — Backend Integrity

| File | Purpose | Tests | Risk | Status |
|------|---------|-------|------|--------|
| `./investigations/backend_integrity/00_STATE.md` | Investigation | N/A | LOW | N/A |
| `./investigations/backend_integrity/01_BACKEND_MAP.md` | Investigation | N/A | LOW | N/A |
| `./investigations/backend_integrity/02_ENDPOINT_INVENTORY.md` | Investigation | N/A | LOW | N/A |
| `./investigations/backend_integrity/03_DATABASE_MODEL_MAP.md` | Investigation | N/A | LOW | N/A |
| `./investigations/backend_integrity/04_MIGRATION_AUDIT.md` | Investigation | N/A | LOW | N/A |
| `./investigations/backend_integrity/05_MODEL_MIGRATION_DRIFT_AUDIT.md` | Investigation | N/A | LOW | N/A |
| `./investigations/backend_integrity/06_API_CONTRACT_AUDIT.md` | Investigation | N/A | LOW | N/A |
| `./investigations/backend_integrity/07_SERVICE_LAYER_AUDIT.md` | Investigation | N/A | LOW | N/A |
| `./investigations/backend_integrity/08_CACHE_AND_BACKGROUND_TASK_AUDIT.md` | Investigation | N/A | LOW | N/A |
| `./investigations/backend_integrity/09_RUNTIME_RISK_AUDIT.md` | Investigation | N/A | LOW | N/A |
| `./investigations/backend_integrity/10_ADVERSARIAL_GRILLING.md` | Investigation | N/A | LOW | N/A |
| `./investigations/backend_integrity/11_CLAUDE_HANDOFF.md` | Investigation | N/A | LOW | N/A |
| `./investigations/backend_integrity/13_CLAUDE_VERIFICATION_REPORT.md` | Investigation | N/A | LOW | N/A |
| `./investigations/backend_integrity/14_FIX_PLAN.md` | Investigation | N/A | LOW | N/A |
| `./investigations/backend_integrity/15_IMPLEMENTATION_REPORT.md` | Investigation | N/A | LOW | N/A |
| `./investigations/backend_integrity/16_TEST_REPORT.md` | Test | N/A | LOW | N/A |
| `./investigations/backend_integrity/17_HEALTH_CHECK_REPORT.md` | Investigation | N/A | LOW | N/A |
| `./investigations/backend_integrity/18_FINAL_ADVERSARIAL_REVIEW.md` | Investigation | N/A | LOW | N/A |
| `./investigations/backend_integrity/19_FINAL_BACKEND_HEALTH_REPORT.md` | Investigation | N/A | LOW | N/A |
## Investigations — Database Integrity

| File | Purpose | Tests | Risk | Status |
|------|---------|-------|------|--------|
| `./investigations/database_integrity/00_STATE.md` | Investigation | N/A | LOW | N/A |
| `./investigations/database_integrity/01_DATABASE_SYSTEM_MAP.md` | Investigation | N/A | LOW | N/A |
| `./investigations/database_integrity/02_MODEL_SCHEMA_MAP.md` | Investigation | N/A | LOW | N/A |
| `./investigations/database_integrity/03_MIGRATION_AUDIT.md` | Investigation | N/A | LOW | N/A |
| `./investigations/database_integrity/04_COLUMN_CONSISTENCY_AUDIT.md` | Investigation | N/A | LOW | N/A |
| `./investigations/database_integrity/05_API_CONTRACT_AUDIT.md` | Investigation | N/A | LOW | N/A |
| `./investigations/database_integrity/06_RELATIONSHIP_AUDIT.md` | Investigation | N/A | LOW | N/A |
| `./investigations/database_integrity/07_ADVERSARIAL_GRILL.md` | Investigation | N/A | LOW | N/A |
| `./investigations/database_integrity/08_HANDOFF_TO_CLAUDE.md` | Investigation | N/A | LOW | N/A |
| `./investigations/database_integrity/10_CLAUDE_VERIFICATION.md` | Investigation | N/A | LOW | N/A |
| `./investigations/database_integrity/11_MIGRATION_FIX_REPORT.md` | Investigation | N/A | LOW | N/A |
| `./investigations/database_integrity/12_MODEL_FIX_REPORT.md` | Investigation | N/A | LOW | N/A |
| `./investigations/database_integrity/13_API_CONTRACT_FIX_REPORT.md` | Investigation | N/A | LOW | N/A |
| `./investigations/database_integrity/14_TEST_REPORT.md` | Test | N/A | LOW | N/A |
| `./investigations/database_integrity/15_FINAL_REVIEW.md` | Investigation | N/A | LOW | N/A |
| `./investigations/database_integrity/16_FINAL_DATABASE_REPAIR_SUMMARY.md` | Investigation | N/A | LOW | N/A |
## Investigations — Morning Briefing

| File | Purpose | Tests | Risk | Status |
|------|---------|-------|------|--------|
| `./investigations/morning_briefing/00_STATE.md` | Investigation | N/A | LOW | N/A |
| `./investigations/morning_briefing/01_SYSTEM_MAP.md` | Investigation | N/A | LOW | N/A |
| `./investigations/morning_briefing/02_REQUEST_FLOW.md` | Investigation | N/A | LOW | N/A |
| `./investigations/morning_briefing/03_CACHE_FLOW.md` | Investigation | N/A | LOW | N/A |
| `./investigations/morning_briefing/04_SCHEDULER_FLOW.md` | Investigation | N/A | LOW | N/A |
| `./investigations/morning_briefing/05_DB_FLOW.md` | Investigation | N/A | LOW | N/A |
| `./investigations/morning_briefing/06_FINDINGS.md` | Investigation | N/A | LOW | N/A |
| `./investigations/morning_briefing/07_ROOT_CAUSES.md` | Investigation | N/A | LOW | N/A |
| `./investigations/morning_briefing/08_FIX_PLAN.md` | Investigation | N/A | LOW | N/A |
| `./investigations/morning_briefing/09_IMPLEMENTATION_REPORT.md` | Investigation | N/A | LOW | N/A |
| `./investigations/morning_briefing/10_CODE_REVIEW.md` | Investigation | N/A | LOW | N/A |
| `./investigations/morning_briefing/11_TEST_STRATEGY.md` | Test | N/A | LOW | N/A |
| `./investigations/morning_briefing/FINAL_REPORT.md` | Investigation | N/A | LOW | N/A |
## Prompts — Backend Improvements

| File | Purpose | Tests | Risk | Status |
|------|---------|-------|------|--------|
| `./prompts/automated backend improvements/rank.md` | AI prompt/plan | N/A | LOW | N/A |
| `./prompts/automated backend improvements/rank_01_pre_compute_nightly_indicators.md` | AI prompt/plan | N/A | LOW | N/A |
| `./prompts/automated backend improvements/rank_02_parallelize_calibration_block.md` | AI prompt/plan | N/A | LOW | N/A |
| `./prompts/automated backend improvements/rank_03_background_pre_fetch_of_live_data.md` | AI prompt/plan | N/A | LOW | N/A |
| `./prompts/automated backend improvements/rank_04_replace_yfinance_with_unified_caching.md` | AI prompt/plan | N/A | LOW | N/A |
| `./prompts/automated backend improvements/rank_05_batch_rrg_quadrant_calculation.md` | AI prompt/plan | N/A | LOW | N/A |
| `./prompts/automated backend improvements/rank_06_optimize_deepseek_reformatter_input.md` | AI prompt/plan | N/A | LOW | N/A |
| `./prompts/automated backend improvements/rank_07_reduce_llm_context_in_risk_analysts.md` | AI prompt/plan | N/A | LOW | N/A |
| `./prompts/automated backend improvements/rank_08_decouple_db_reads_from_analysis_thread.md` | AI prompt/plan | N/A | LOW | N/A |
| `./prompts/automated backend improvements/rank_09_implement_sse_streaming_for_ui.md` | AI prompt/plan | N/A | LOW | N/A |
| `./prompts/automated backend improvements/rank_10_async_langgraph_agent_execution.md` | AI prompt/plan | N/A | LOW | N/A |
| `./prompts/automated backend improvements/rank_11_shift_hmm_regime_logic_to_c_rust.md` | AI prompt/plan | N/A | LOW | N/A |
| `./prompts/automated backend improvements/rank_12_parallelize_pdf_filings_ocr.md` | AI prompt/plan | N/A | LOW | N/A |
| `./prompts/automated backend improvements/rank_13_replace_slow_selenium_bs4_scraping.md` | AI prompt/plan | N/A | LOW | N/A |
| `./prompts/automated backend improvements/rank_14_optimize_analysishistory_json_serialization.md` | AI prompt/plan | N/A | LOW | N/A |
| `./prompts/automated backend improvements/rank_15_convert_synchronous_requests_to_aiohttp.md` | AI prompt/plan | N/A | LOW | N/A |
| `./prompts/automated backend improvements/rank_16_math_replacing_ai___piotroski_beneish.md` | AI prompt/plan | N/A | LOW | N/A |
| `./prompts/automated backend improvements/rank_17_math_replacing_ai___momentum_divergence.md` | AI prompt/plan | N/A | LOW | N/A |
| `./prompts/automated backend improvements/rank_18_math_replacing_ai___pcr_and_gex.md` | AI prompt/plan | N/A | LOW | N/A |
| `./prompts/automated backend improvements/rank_19_math_replacing_ai___relative_rotation_graph.md` | AI prompt/plan | N/A | LOW | N/A |
| `./prompts/automated backend improvements/rank_20_math_replacing_ai___conformal_prediction.md` | AI prompt/plan | N/A | LOW | N/A |
| `./prompts/automated backend improvements/rank_21_math_replacing_ai___euclidean_analogues.md` | AI prompt/plan | N/A | LOW | N/A |
| `./prompts/automated backend improvements/rank_22_math_replacing_ai___deterministic_dcf.md` | AI prompt/plan | N/A | LOW | N/A |
| `./prompts/automated backend improvements/rank_23_math_replacing_ai___volume_isolation_forest.md` | AI prompt/plan | N/A | LOW | N/A |
| `./prompts/automated backend improvements/rank_24_math_replacing_ai___eps_drift_model.md` | AI prompt/plan | N/A | LOW | N/A |
| `./prompts/automated backend improvements/rank_25_math_replacing_ai___finbert_embeddings.md` | AI prompt/plan | N/A | LOW | N/A |
| `./prompts/automated backend improvements/rank_26_math_replacing_ai___minskyan_risk_flows.md` | AI prompt/plan | N/A | LOW | N/A |
| `./prompts/automated backend improvements/rank_27_math_replacing_ai___signal_agreement_multiplier.md` | AI prompt/plan | N/A | LOW | N/A |
| `./prompts/automated backend improvements/rank_28_math_replacing_ai___dtw_pattern_matching.md` | AI prompt/plan | N/A | LOW | N/A |
| `./prompts/automated backend improvements/rank_29_math_replacing_ai___portfolio_correlation_matrix.md` | AI prompt/plan | N/A | LOW | N/A |
| `./prompts/automated backend improvements/rank_30_math_replacing_ai___auditor_risk_quantification.md` | AI prompt/plan | N/A | LOW | N/A |
| `./prompts/automated backend improvements/rank_31_remove_hardcoded_sector_pe_map.md` | AI prompt/plan | N/A | LOW | N/A |
| `./prompts/automated backend improvements/rank_32_remove_hardcoded_14_day_cutoff.md` | AI prompt/plan | N/A | LOW | N/A |
| `./prompts/automated backend improvements/rank_33_remove_hardcoded_nse_bse_suffixes.md` | AI prompt/plan | N/A | LOW | N/A |
| `./prompts/automated backend improvements/rank_34_remove_hardcoded_yfinance_sleep_intervals.md` | AI prompt/plan | N/A | LOW | N/A |
| `./prompts/automated backend improvements/rank_35_move_signal_maps_to_db.md` | AI prompt/plan | N/A | LOW | N/A |
| `./prompts/automated backend improvements/rank_36_make_deepseek_truncation_dynamic.md` | AI prompt/plan | N/A | LOW | N/A |
| `./prompts/automated backend improvements/rank_37_eliminate_hardcoded_token_limits.md` | AI prompt/plan | N/A | LOW | N/A |
| `./prompts/automated backend improvements/rank_38_configurable_yfinance_circuit_breaker.md` | AI prompt/plan | N/A | LOW | N/A |
| `./prompts/automated backend improvements/rank_39_centralize_cache_ttls.md` | AI prompt/plan | N/A | LOW | N/A |
| `./prompts/automated backend improvements/rank_40_remove_hardcoded_user_agents.md` | AI prompt/plan | N/A | LOW | N/A |
| `./prompts/automated backend improvements/rank_41_migrate_system_prompts_to_db.md` | AI prompt/plan | N/A | LOW | N/A |
| `./prompts/automated backend improvements/rank_42_refactor_hardcoded_ticker_overrides.md` | AI prompt/plan | N/A | LOW | N/A |
| `./prompts/automated backend improvements/rank_43_remove_hardcoded_row_limits.md` | AI prompt/plan | N/A | LOW | N/A |
| `./prompts/automated backend improvements/rank_44_fix_hardcoded_http_timeouts.md` | AI prompt/plan | N/A | LOW | N/A |
| `./prompts/automated backend improvements/rank_45_extract_max_debate_rounds.md` | AI prompt/plan | N/A | LOW | N/A |
| `./prompts/automated backend improvements/rank_46_fix_path_shadowing_in_worker.md` | AI prompt/plan | N/A | LOW | N/A |
| `./prompts/automated backend improvements/rank_47_robust_deepseek_error_handling.md` | AI prompt/plan | N/A | LOW | N/A |
| `./prompts/automated backend improvements/rank_48_implement_sqlalchemy_connection_pooling.md` | AI prompt/plan | N/A | LOW | N/A |
| `./prompts/automated backend improvements/rank_49_fix_ordereddict_memory_leak.md` | AI prompt/plan | N/A | LOW | N/A |
| `./prompts/automated backend improvements/rank_50_standardize_timezone_awareness.md` | AI prompt/plan | N/A | LOW | N/A |
| `./prompts/automated backend improvements/rank_51_background_worker_dead_letter_queue.md` | AI prompt/plan | N/A | LOW | N/A |
| `./prompts/automated backend improvements/rank_52_migrate_from_multiprocessing_to_celery.md` | AI prompt/plan | N/A | LOW | N/A |
| `./prompts/automated backend improvements/rank_53_fix_pure_function_state_mutation.md` | AI prompt/plan | N/A | LOW | N/A |
| `./prompts/automated backend improvements/rank_54_global_yfinance_rate_limit_handling.md` | AI prompt/plan | N/A | LOW | N/A |
| `./prompts/automated backend improvements/rank_55_add_unit_tests_for_calibration_engine.md` | AI prompt/plan | N/A | LOW | N/A |
| `./prompts/automated backend improvements/rank_56_create__healthz_system_check.md` | AI prompt/plan | N/A | LOW | N/A |
| `./prompts/automated backend improvements/rank_57_standardize_structured_logging.md` | AI prompt/plan | N/A | LOW | N/A |
| `./prompts/automated backend improvements/rank_58_strict_pydantic_input_validation.md` | AI prompt/plan | N/A | LOW | N/A |
| `./prompts/automated backend improvements/rank_59_unify_the_fragmentation_of_caches.md` | AI prompt/plan | N/A | LOW | N/A |
| `./prompts/automated backend improvements/rank_60_clean_up_monolithic_legacy_code.md` | AI prompt/plan | N/A | LOW | N/A |
## Prompts — Frontend Improvements

| File | Purpose | Tests | Risk | Status |
|------|---------|-------|------|--------|
| `./prompts/automated frontend improvements/rank.md` | AI prompt/plan | N/A | LOW | N/A |
| `./prompts/automated frontend improvements/rank_01_build_pkscreenerview.md` | AI prompt/plan | N/A | LOW | N/A |
| `./prompts/automated frontend improvements/rank_02_build_macrodashboardview.md` | AI prompt/plan | N/A | LOW | N/A |
| `./prompts/automated frontend improvements/rank_03_build_datafreshnesshud.md` | AI prompt/plan | N/A | LOW | N/A |
| `./prompts/automated frontend improvements/rank_04_implement_pdfuploadview_for_rag.md` | AI prompt/plan | N/A | LOW | N/A |
| `./prompts/automated frontend improvements/rank_05_create_analysistimelineview.md` | AI prompt/plan | N/A | LOW | N/A |
| `./prompts/automated frontend improvements/rank_06_build_piotroskibreakdownsheet.md` | AI prompt/plan | N/A | LOW | N/A |
| `./prompts/automated frontend improvements/rank_07_build_optionsmicrostructurescreen.md` | AI prompt/plan | N/A | LOW | N/A |
| `./prompts/automated frontend improvements/rank_08_create_advisorvideoplayer.md` | AI prompt/plan | N/A | LOW | N/A |
| `./prompts/automated frontend improvements/rank_09_implement_screenerfiltersheet.md` | AI prompt/plan | N/A | LOW | N/A |
| `./prompts/automated frontend improvements/rank_10_build_strategyexecutionview.md` | AI prompt/plan | N/A | LOW | N/A |
| `./prompts/automated frontend improvements/rank_11_implement_feedbackinjectorui.md` | AI prompt/plan | N/A | LOW | N/A |
| `./prompts/automated frontend improvements/rank_12_build_sectorrotationheatmap.md` | AI prompt/plan | N/A | LOW | N/A |
| `./prompts/automated frontend improvements/rank_13_remove_hardcoded_192.168.1.122_url.md` | AI prompt/plan | N/A | LOW | N/A |
| `./prompts/automated frontend improvements/rank_14_fix_hardcoded_network_timeouts.md` | AI prompt/plan | N/A | LOW | N/A |
| `./prompts/automated frontend improvements/rank_15_enforce_theme.spacing_strictly.md` | AI prompt/plan | N/A | LOW | N/A |
| `./prompts/automated frontend improvements/rank_16_remove_hardcoded_system_fonts.md` | AI prompt/plan | N/A | LOW | N/A |
| `./prompts/automated frontend improvements/rank_17_replace_hardcoded_hex_colors.md` | AI prompt/plan | N/A | LOW | N/A |
| `./prompts/automated frontend improvements/rank_18_remove_200_char_error_limits.md` | AI prompt/plan | N/A | LOW | N/A |
| `./prompts/automated frontend improvements/rank_19_dynamic_signal_mapping.md` | AI prompt/plan | N/A | LOW | N/A |
| `./prompts/automated frontend improvements/rank_20_extract_timezone_identifier.md` | AI prompt/plan | N/A | LOW | N/A |
| `./prompts/automated frontend improvements/rank_21_standardize_corner_radii.md` | AI prompt/plan | N/A | LOW | N/A |
| `./prompts/automated frontend improvements/rank_22_extract_animation_durations.md` | AI prompt/plan | N/A | LOW | N/A |
| `./prompts/automated frontend improvements/rank_23_dynamic_chart_domain_bounds.md` | AI prompt/plan | N/A | LOW | N/A |
| `./prompts/automated frontend improvements/rank_24_move_placeholders_to_localizable.strings.md` | AI prompt/plan | N/A | LOW | N/A |
| `./prompts/automated frontend improvements/rank_25_backend_driven_regex_for_tickers.md` | AI prompt/plan | N/A | LOW | N/A |
| `./prompts/automated frontend improvements/rank_26_extract_batch_analysis_limit.md` | AI prompt/plan | N/A | LOW | N/A |
| `./prompts/automated frontend improvements/rank_27_implement_endpoint_enum_router.md` | AI prompt/plan | N/A | LOW | N/A |
| `./prompts/automated frontend improvements/rank_28_enforce_ekpressstyle_globally.md` | AI prompt/plan | N/A | LOW | N/A |
| `./prompts/automated frontend improvements/rank_29_enforce_haptic_feedback.md` | AI prompt/plan | N/A | LOW | N/A |
| `./prompts/automated frontend improvements/rank_30_replace_standard_divider.md` | AI prompt/plan | N/A | LOW | N/A |
| `./prompts/automated frontend improvements/rank_31_themed_scroll_indicators.md` | AI prompt/plan | N/A | LOW | N/A |
| `./prompts/automated frontend improvements/rank_32_enforce_banknotecard_modifier.md` | AI prompt/plan | N/A | LOW | N/A |
| `./prompts/automated frontend improvements/rank_33_apply_stampappear_modifier.md` | AI prompt/plan | N/A | LOW | N/A |
| `./prompts/automated frontend improvements/rank_34_add_rupeewatermark_globally.md` | AI prompt/plan | N/A | LOW | N/A |
| `./prompts/automated frontend improvements/rank_35_enhance_governorsealavatar.md` | AI prompt/plan | N/A | LOW | N/A |
| `./prompts/automated frontend improvements/rank_36_enforce_indianformatter.formatlakhscrores.md` | AI prompt/plan | N/A | LOW | N/A |
| `./prompts/automated frontend improvements/rank_37_fix_unidirectional_data_flow.md` | AI prompt/plan | N/A | LOW | N/A |
| `./prompts/automated frontend improvements/rank_38_enforce_infinity_max_width.md` | AI prompt/plan | N/A | LOW | N/A |
| `./prompts/automated frontend improvements/rank_39_forbid_geometryreader_in_hstacks.md` | AI prompt/plan | N/A | LOW | N/A |
| `./prompts/automated frontend improvements/rank_40_implement_numerictext_transitions.md` | AI prompt/plan | N/A | LOW | N/A |
| `./prompts/automated frontend improvements/rank_41_replace_blocking_spinners_with_skeletons.md` | AI prompt/plan | N/A | LOW | N/A |
| `./prompts/automated frontend improvements/rank_42_respect_reducemotion_accessibility.md` | AI prompt/plan | N/A | LOW | N/A |
| `./prompts/automated frontend improvements/rank_43_complete_async_await_migration.md` | AI prompt/plan | N/A | LOW | N/A |
| `./prompts/automated frontend improvements/rank_44_implement_nscache_imagecache.md` | AI prompt/plan | N/A | LOW | N/A |
| `./prompts/automated frontend improvements/rank_45_break_down_stockdatabase.md` | AI prompt/plan | N/A | LOW | N/A |
| `./prompts/automated frontend improvements/rank_46_lazy_load_analysisscreen_components.md` | AI prompt/plan | N/A | LOW | N/A |
| `./prompts/automated frontend improvements/rank_47_remove_redundant_onappear_fetches.md` | AI prompt/plan | N/A | LOW | N/A |
| `./prompts/automated frontend improvements/rank_48_implement_search_debounce.md` | AI prompt/plan | N/A | LOW | N/A |
| `./prompts/automated frontend improvements/rank_49_cache_jsondecoder_instance.md` | AI prompt/plan | N/A | LOW | N/A |
| `./prompts/automated frontend improvements/rank_50_implement_offline_mode.md` | AI prompt/plan | N/A | LOW | N/A |
| `./prompts/automated frontend improvements/rank_51_fix_portfolioscreen_full_state_reloads.md` | AI prompt/plan | N/A | LOW | N/A |
| `./prompts/automated frontend improvements/rank_52_fix_homefeedviewmodel_memory_leaks.md` | AI prompt/plan | N/A | LOW | N/A |
| `./prompts/automated frontend improvements/rank_53_move_chart_calculations_to_background_task.md` | AI prompt/plan | N/A | LOW | N/A |
| `./prompts/automated frontend improvements/rank_54_audit_environmentobject_over_invalidation.md` | AI prompt/plan | N/A | LOW | N/A |
| `./prompts/automated frontend improvements/rank_55_split_models.swift_monolith.md` | AI prompt/plan | N/A | LOW | N/A |
| `./prompts/automated frontend improvements/rank_56_network_retry_with_exponential_backoff.md` | AI prompt/plan | N/A | LOW | N/A |
## Prompts

| File | Purpose | Tests | Risk | Status |
|------|---------|-------|------|--------|
| `./prompts/AI_DATA_PIPELINE_UPGRADE_PROMPT.md` | Documentation | N/A | LOW | N/A |
| `./prompts/BETTER_AI_ANALYSIS_PROMPT.md` | Documentation | N/A | LOW | N/A |
| `./prompts/CORRELATION_MATRIX_MATH_UPGRADE_PROMPT.md` | Documentation | N/A | LOW | N/A |
| `./prompts/EXTREME_ANALYSIS_UPGRADE_PROMPT.md` | Documentation | N/A | LOW | N/A |
| `./prompts/ML_HYBRID_PIPELINE_CHECKLIST.md` | Documentation | N/A | LOW | N/A |
| `./prompts/ML_HYBRID_PIPELINE_PROMPT.md` | Documentation | N/A | LOW | N/A |
| `./prompts/OPTIONS_STRATEGY_BUILDER_PROMPT.md` | Documentation | N/A | LOW | N/A |
| `./prompts/QUANT_INSPECTOR_UI_PROMPT.md` | Documentation | N/A | LOW | N/A |
| `./prompts/REMOVE_HARDCODED_VALUES_PROMPT.md` | Documentation | N/A | LOW | N/A |
| `./prompts/SPEED_OPTIMIZATION_PROMPT.md` | Documentation | N/A | LOW | N/A |
| `./prompts/TEST_BACKEND_PROMPT.md` | Test | N/A | LOW | N/A |
| `./prompts/VECTOR_DB_RAG_PROMPT.md` | Documentation | N/A | LOW | N/A |
| `./prompts/poke_holes_fixes.md` | Documentation | N/A | LOW | N/A |
## Proposals

| File | Purpose | Tests | Risk | Status |
|------|---------|-------|------|--------|
| `./proposals/ai_analysis_workflow_report.md` | Documentation | N/A | LOW | N/A |
| `./proposals/architecture_deepening_report.html` | HTML | N/A | LOW | N/A |
| `./proposals/database_reliability_audit.html` | HTML | N/A | LOW | N/A |
| `./proposals/ml_flywheel_proposal.md` | Documentation | N/A | LOW | N/A |
| `./proposals/poke_holes.md` | Documentation | N/A | LOW | N/A |
## Research — Stress Test Upgrade

| File | Purpose | Tests | Risk | Status |
|------|---------|-------|------|--------|
| `./research/stress_test_upgrade/API_CHANGES.md` | Documentation | N/A | LOW | N/A |
| `./research/stress_test_upgrade/CURRENT_STATE.md` | Documentation | N/A | LOW | N/A |
| `./research/stress_test_upgrade/DATABASE_CHANGES.md` | Documentation | N/A | LOW | N/A |
| `./research/stress_test_upgrade/FINAL_CHECKLIST.md` | Documentation | N/A | LOW | N/A |
| `./research/stress_test_upgrade/FRONTEND_CHANGES.md` | Documentation | N/A | LOW | N/A |
| `./research/stress_test_upgrade/GAP_ANALYSIS.md` | Documentation | N/A | LOW | N/A |
| `./research/stress_test_upgrade/IMPLEMENTATION_ORDER.md` | Documentation | N/A | LOW | N/A |
| `./research/stress_test_upgrade/IMPLEMENTATION_ROADMAP.md` | Documentation | N/A | LOW | N/A |
| `./research/stress_test_upgrade/QUANT_MODEL_SPEC.md` | Documentation | N/A | LOW | N/A |
| `./research/stress_test_upgrade/RISKS_AND_DEPENDENCIES.md` | Documentation | N/A | LOW | N/A |
| `./research/stress_test_upgrade/SPEC_REQUIREMENTS.md` | Python dependencies | N/A | LOW | N/A |
| `./research/stress_test_upgrade/TASK_BREAKDOWN.md` | Documentation | N/A | LOW | N/A |
## CodebaseInformation

| File | Purpose | Tests | Risk | Status |
|------|---------|-------|------|--------|
| `./CodebaseInformation/API_CONTRACT_MAP.md` | Documentation | N/A | LOW | N/A |
| `./CodebaseInformation/APP_NAVIGATION_MAP.md` | Documentation | N/A | LOW | N/A |
| `./CodebaseInformation/ARCHITECTURE.md` | Documentation | N/A | LOW | N/A |
| `./CodebaseInformation/ARCHITECTURE_MAP.md` | Documentation | N/A | LOW | N/A |
| `./CodebaseInformation/LLM_CREDITS_USAGE.md` | Documentation | N/A | LOW | N/A |
## TODO Lists

| File | Purpose | Tests | Risk | Status |
|------|---------|-------|------|--------|
| `./TODO/2026-06-08_0223_ui-modernization-and-87-edge-case-fixes.md` | Documentation | N/A | LOW | N/A |
| `./TODO/2026-06-08_50-improvements-frontend-backend.md` | Documentation | N/A | LOW | N/A |
| `./TODO/PLAN.md` | Documentation | N/A | LOW | N/A |
## Scripts (Root)

| File | Purpose | Tests | Risk | Status |
|------|---------|-------|------|--------|
| `./scripts/.remember/.gitignore` | Git/cache metadata | N/A | LOW | N/A |
| `./scripts/.remember/logs/hook-errors.log` | Log | N/A | LOW | N/A |
| `./scripts/.remember/logs/memory-2026-06-15.log` | Log | N/A | LOW | N/A |
| `./scripts/check_stock.sh` | Shell script | N/A | LOW | N/A |
| `./scripts/check_stress_test.sh` | Shell script | N/A | LOW | N/A |
| `./scripts/checklength.sh` | Shell script | N/A | LOW | N/A |
| `./scripts/lint_crash_patterns.sh` | Shell script | N/A | LOW | N/A |
| `./scripts/run_analysis.sh` | Shell script | N/A | LOW | N/A |
| `./scripts/show_analysis.sh` | Shell script | N/A | LOW | N/A |
## StockMe (Root)

| File | Purpose | Tests | Risk | Status |
|------|---------|-------|------|--------|
| `./stockme/StockDatabase.swift` | Swift source | N/A | HIGH | N/A |
## GitHub Actions

| File | Purpose | Tests | Risk | Status |
|------|---------|-------|------|--------|
| `./.github/workflows/pr-visual-recap.yml` | YAML config | N/A | LOW | N/A |
## Agent Artifacts

| File | Purpose | Tests | Risk | Status |
|------|---------|-------|------|--------|
| `./.agent-artifacts/nl-screener-fix/00_REPO_MAP.md` | Documentation | N/A | LOW | N/A |
| `./.agent-artifacts/nl-screener-fix/01_DATA_FLOW_TRACE.md` | Documentation | N/A | LOW | N/A |
| `./.agent-artifacts/nl-screener-fix/02_FRONTEND_BACKEND_CONTRACT_DIFF.md` | Documentation | N/A | LOW | N/A |
| `./.agent-artifacts/nl-screener-fix/03_ROOT_CAUSE_HYPOTHESES.md` | Documentation | N/A | LOW | N/A |
| `./.agent-artifacts/nl-screener-fix/04_IMPLEMENTATION_PLAN_FOR_CLAUDE.md` | Documentation | N/A | LOW | N/A |
| `./.agent-artifacts/nl-screener-fix/05_TEST_PLAN.md` | Test | N/A | LOW | N/A |
| `./.agent-artifacts/nl-screener-fix/06_IMPLEMENTATION_SUMMARY.md` | Documentation | N/A | LOW | N/A |
| `./.agent-artifacts/nl-screener-fix/07_FINAL_CONTRACT.md` | Documentation | N/A | LOW | N/A |
| `./.agent-artifacts/nl-screener-fix/08_TEST_RESULTS.md` | Test | N/A | LOW | N/A |
| `./.agent-artifacts/nl-screener-fix/09_REMAINING_RISKS.md` | Documentation | N/A | LOW | N/A |
| `./.agent-artifacts/nl-screener-fix/10_TEST_GENERATION_SUMMARY.md` | Test | N/A | LOW | N/A |
| `./.agent-artifacts/nl-screener-fix/11_EDGE_CASE_MATRIX.md` | Documentation | N/A | LOW | N/A |
| `./.agent-artifacts/nl-screener-fix/12_REGRESSION_COVERAGE.md` | Documentation | N/A | LOW | N/A |
| `./.agent-artifacts/nl-screener-fix/13_DEEPSEEK_TEST_RUN_RESULTS.md` | Test | N/A | LOW | N/A |
## SpecKit Configuration

| File | Purpose | Tests | Risk | Status |
|------|---------|-------|------|--------|
| `./.specify/extensions.yml` | SpecKit | N/A | LOW | N/A |
| `./.specify/extensions/.registry` | SpecKit | N/A | LOW | N/A |
| `./.specify/extensions/agent-context/README.md` | Documentation | N/A | LOW | N/A |
| `./.specify/extensions/agent-context/agent-context-config.yml` | SpecKit | N/A | LOW | N/A |
| `./.specify/extensions/agent-context/commands/speckit.agent-context.update.md` | SpecKit | N/A | LOW | N/A |
| `./.specify/extensions/agent-context/extension.yml` | SpecKit | N/A | LOW | N/A |
| `./.specify/extensions/agent-context/scripts/bash/update-agent-context.sh` | SpecKit | N/A | LOW | N/A |
| `./.specify/extensions/agent-context/scripts/powershell/update-agent-context.ps1` | SpecKit | N/A | LOW | N/A |
| `./.specify/init-options.json` | SpecKit | N/A | LOW | N/A |
| `./.specify/integration.json` | SpecKit | N/A | LOW | N/A |
| `./.specify/integrations/claude.manifest.json` | SpecKit | N/A | LOW | N/A |
| `./.specify/integrations/speckit.manifest.json` | SpecKit | N/A | LOW | N/A |
| `./.specify/memory/constitution.md` | SpecKit | N/A | LOW | N/A |
| `./.specify/scripts/bash/check-prerequisites.sh` | SpecKit | N/A | LOW | N/A |
| `./.specify/scripts/bash/common.sh` | SpecKit | N/A | LOW | N/A |
| `./.specify/scripts/bash/create-new-feature.sh` | SpecKit | N/A | LOW | N/A |
| `./.specify/scripts/bash/setup-plan.sh` | SpecKit | N/A | LOW | N/A |
| `./.specify/scripts/bash/setup-tasks.sh` | SpecKit | N/A | LOW | N/A |
| `./.specify/templates/checklist-template.md` | SpecKit | N/A | LOW | N/A |
| `./.specify/templates/constitution-template.md` | SpecKit | N/A | LOW | N/A |
| `./.specify/templates/plan-template.md` | SpecKit | N/A | LOW | N/A |
| `./.specify/templates/spec-template.md` | SpecKit | N/A | LOW | N/A |
| `./.specify/templates/tasks-template.md` | SpecKit | N/A | LOW | N/A |
| `./.specify/workflows/speckit/workflow.yml` | SpecKit | N/A | LOW | N/A |
| `./.specify/workflows/workflow-registry.json` | SpecKit | N/A | LOW | N/A |
## Claude Skills

| File | Purpose | Tests | Risk | Status |
|------|---------|-------|------|--------|
| `./.claude/skills/gitnexus/gitnexus-cli/SKILL.md` | Skill | N/A | LOW | N/A |
| `./.claude/skills/gitnexus/gitnexus-debugging/SKILL.md` | Skill | N/A | LOW | N/A |
| `./.claude/skills/gitnexus/gitnexus-exploring/SKILL.md` | Skill | N/A | LOW | N/A |
| `./.claude/skills/gitnexus/gitnexus-guide/SKILL.md` | Skill | N/A | LOW | N/A |
| `./.claude/skills/gitnexus/gitnexus-impact-analysis/SKILL.md` | Skill | N/A | LOW | N/A |
| `./.claude/skills/gitnexus/gitnexus-refactoring/SKILL.md` | Skill | N/A | LOW | N/A |
| `./.claude/skills/speckit-agent-context-update/SKILL.md` | Skill | N/A | LOW | N/A |
| `./.claude/skills/speckit-analyze/SKILL.md` | Skill | N/A | LOW | N/A |
| `./.claude/skills/speckit-checklist/SKILL.md` | Skill | N/A | LOW | N/A |
| `./.claude/skills/speckit-clarify/SKILL.md` | Skill | N/A | LOW | N/A |
| `./.claude/skills/speckit-constitution/SKILL.md` | Skill | N/A | LOW | N/A |
| `./.claude/skills/speckit-implement/SKILL.md` | Skill | N/A | LOW | N/A |
| `./.claude/skills/speckit-plan/SKILL.md` | Skill | N/A | LOW | N/A |
| `./.claude/skills/speckit-specify/SKILL.md` | Skill | N/A | LOW | N/A |
| `./.claude/skills/speckit-tasks/SKILL.md` | Skill | N/A | LOW | N/A |
| `./.claude/skills/speckit-taskstoissues/SKILL.md` | Skill | N/A | LOW | N/A |
| `./.claude/skills/ui-ux-pro-max/SKILL.md` | Skill | N/A | LOW | N/A |
| `./.claude/skills/ui-ux-pro-max/data/charts.csv` | Skill | N/A | LOW | N/A |
| `./.claude/skills/ui-ux-pro-max/data/colors.csv` | Skill | N/A | LOW | N/A |
| `./.claude/skills/ui-ux-pro-max/data/icons.csv` | Skill | N/A | LOW | N/A |
| `./.claude/skills/ui-ux-pro-max/data/landing.csv` | Skill | N/A | LOW | N/A |
| `./.claude/skills/ui-ux-pro-max/data/products.csv` | Skill | N/A | LOW | N/A |
| `./.claude/skills/ui-ux-pro-max/data/react-performance.csv` | Skill | N/A | LOW | N/A |
| `./.claude/skills/ui-ux-pro-max/data/stacks/astro.csv` | Skill | N/A | LOW | N/A |
| `./.claude/skills/ui-ux-pro-max/data/stacks/flutter.csv` | Skill | N/A | LOW | N/A |
| `./.claude/skills/ui-ux-pro-max/data/stacks/html-tailwind.csv` | Skill | N/A | LOW | N/A |
| `./.claude/skills/ui-ux-pro-max/data/stacks/jetpack-compose.csv` | Skill | N/A | LOW | N/A |
| `./.claude/skills/ui-ux-pro-max/data/stacks/nextjs.csv` | Skill | N/A | LOW | N/A |
| `./.claude/skills/ui-ux-pro-max/data/stacks/nuxt-ui.csv` | Skill | N/A | LOW | N/A |
| `./.claude/skills/ui-ux-pro-max/data/stacks/nuxtjs.csv` | Skill | N/A | LOW | N/A |
| `./.claude/skills/ui-ux-pro-max/data/stacks/react-native.csv` | Skill | N/A | LOW | N/A |
| `./.claude/skills/ui-ux-pro-max/data/stacks/react.csv` | Skill | N/A | LOW | N/A |
| `./.claude/skills/ui-ux-pro-max/data/stacks/shadcn.csv` | Skill | N/A | LOW | N/A |
| `./.claude/skills/ui-ux-pro-max/data/stacks/svelte.csv` | Skill | N/A | LOW | N/A |
| `./.claude/skills/ui-ux-pro-max/data/stacks/swiftui.csv` | Skill | N/A | LOW | N/A |
| `./.claude/skills/ui-ux-pro-max/data/stacks/vue.csv` | Skill | N/A | LOW | N/A |
| `./.claude/skills/ui-ux-pro-max/data/styles.csv` | Skill | N/A | LOW | N/A |
| `./.claude/skills/ui-ux-pro-max/data/typography.csv` | Skill | N/A | LOW | N/A |
| `./.claude/skills/ui-ux-pro-max/data/ui-reasoning.csv` | Skill | N/A | LOW | N/A |
| `./.claude/skills/ui-ux-pro-max/data/ux-guidelines.csv` | Skill | N/A | LOW | N/A |
| `./.claude/skills/ui-ux-pro-max/data/web-interface.csv` | Skill | N/A | LOW | N/A |
| `./.claude/skills/ui-ux-pro-max/scripts/core.py` | Skill | NO | LOW | untested |
| `./.claude/skills/ui-ux-pro-max/scripts/design_system.py` | Skill | NO | LOW | untested |
| `./.claude/skills/ui-ux-pro-max/scripts/search.py` | Skill | NO | LOW | untested |
## Claude Worktrees (Copy)

| File | Purpose | Tests | Risk | Status |
|------|---------|-------|------|--------|
| `./.claude/worktrees/agent-a221efa2bcbf5bf06/.claude/settings.local.json` | JSON/config | N/A | LOW | N/A |
| `./.claude/worktrees/agent-a221efa2bcbf5bf06/.git` |  file | N/A | LOW | N/A |
| `./.claude/worktrees/agent-a221efa2bcbf5bf06/.gitignore` | Git/cache metadata | N/A | LOW | N/A |
| `./.claude/worktrees/agent-a221efa2bcbf5bf06/.specify/extensions.yml` | YAML config | N/A | LOW | N/A |
| `./.claude/worktrees/agent-a221efa2bcbf5bf06/.specify/extensions/.registry` |  file | N/A | LOW | N/A |
| `./.claude/worktrees/agent-a221efa2bcbf5bf06/.specify/extensions/agent-context/README.md` | Documentation | N/A | LOW | N/A |
| `./.claude/worktrees/agent-a221efa2bcbf5bf06/.specify/extensions/agent-context/agent-context-config.yml` | YAML config | N/A | LOW | N/A |
| `./.claude/worktrees/agent-a221efa2bcbf5bf06/.specify/extensions/agent-context/commands/speckit.agent-context.update.md` | Documentation | N/A | LOW | N/A |
| `./.claude/worktrees/agent-a221efa2bcbf5bf06/.specify/extensions/agent-context/extension.yml` | YAML config | N/A | LOW | N/A |
| `./.claude/worktrees/agent-a221efa2bcbf5bf06/.specify/extensions/agent-context/scripts/bash/update-agent-context.sh` | Shell script | N/A | LOW | N/A |
| `./.claude/worktrees/agent-a221efa2bcbf5bf06/.specify/extensions/agent-context/scripts/powershell/update-agent-context.ps1` | .ps1 file | N/A | LOW | N/A |
| `./.claude/worktrees/agent-a221efa2bcbf5bf06/.specify/init-options.json` | JSON/config | N/A | LOW | N/A |
| `./.claude/worktrees/agent-a221efa2bcbf5bf06/.specify/integration.json` | JSON/config | N/A | LOW | N/A |
| `./.claude/worktrees/agent-a221efa2bcbf5bf06/.specify/integrations/claude.manifest.json` | JSON/config | N/A | LOW | N/A |
| `./.claude/worktrees/agent-a221efa2bcbf5bf06/.specify/integrations/speckit.manifest.json` | JSON/config | N/A | LOW | N/A |
| `./.claude/worktrees/agent-a221efa2bcbf5bf06/.specify/memory/constitution.md` | Documentation | N/A | LOW | N/A |
| `./.claude/worktrees/agent-a221efa2bcbf5bf06/.specify/scripts/bash/check-prerequisites.sh` | Shell script | N/A | LOW | N/A |
| `./.claude/worktrees/agent-a221efa2bcbf5bf06/.specify/scripts/bash/common.sh` | Shell script | N/A | LOW | N/A |
| `./.claude/worktrees/agent-a221efa2bcbf5bf06/.specify/scripts/bash/create-new-feature.sh` | Shell script | N/A | LOW | N/A |
| `./.claude/worktrees/agent-a221efa2bcbf5bf06/.specify/scripts/bash/setup-plan.sh` | Shell script | N/A | LOW | N/A |
| `./.claude/worktrees/agent-a221efa2bcbf5bf06/.specify/scripts/bash/setup-tasks.sh` | Shell script | N/A | LOW | N/A |
| `./.claude/worktrees/agent-a221efa2bcbf5bf06/.specify/templates/checklist-template.md` | Documentation | N/A | LOW | N/A |
| `./.claude/worktrees/agent-a221efa2bcbf5bf06/.specify/templates/constitution-template.md` | Documentation | N/A | LOW | N/A |
| `./.claude/worktrees/agent-a221efa2bcbf5bf06/.specify/templates/plan-template.md` | Documentation | N/A | LOW | N/A |
| `./.claude/worktrees/agent-a221efa2bcbf5bf06/.specify/templates/spec-template.md` | Documentation | N/A | LOW | N/A |
| `./.claude/worktrees/agent-a221efa2bcbf5bf06/.specify/templates/tasks-template.md` | Documentation | N/A | LOW | N/A |
| `./.claude/worktrees/agent-a221efa2bcbf5bf06/.specify/workflows/speckit/workflow.yml` | YAML config | N/A | LOW | N/A |
| `./.claude/worktrees/agent-a221efa2bcbf5bf06/.specify/workflows/workflow-registry.json` | JSON/config | N/A | LOW | N/A |
| `./.claude/worktrees/agent-a221efa2bcbf5bf06/AGENTS.md` | Documentation | N/A | LOW | N/A |
| `./.claude/worktrees/agent-a221efa2bcbf5bf06/CLAUDE.md` | Documentation | N/A | LOW | N/A |
| `./.claude/worktrees/agent-a221efa2bcbf5bf06/CodebaseInformation/API_CONTRACT_MAP.md` | Documentation | N/A | LOW | N/A |
| `./.claude/worktrees/agent-a221efa2bcbf5bf06/CodebaseInformation/ARCHITECTURE.md` | Documentation | N/A | LOW | N/A |
| `./.claude/worktrees/agent-a221efa2bcbf5bf06/CodebaseInformation/ARCHITECTURE_MAP.md` | Documentation | N/A | LOW | N/A |
| `./.claude/worktrees/agent-a221efa2bcbf5bf06/CodebaseInformation/LLM_CREDITS_USAGE.md` | Documentation | N/A | LOW | N/A |
| `./.claude/worktrees/agent-a221efa2bcbf5bf06/CodebaseInformation/MEGA_TODO.md` | Documentation | N/A | LOW | N/A |
| `./.claude/worktrees/agent-a221efa2bcbf5bf06/CodebaseInformation/NIVESH_TODO.md` | Documentation | N/A | LOW | N/A |
| `./.claude/worktrees/agent-a221efa2bcbf5bf06/CodebaseInformation/OVERNIGHT_LEDGER.md` | Documentation | N/A | LOW | N/A |
| `./.claude/worktrees/agent-a221efa2bcbf5bf06/CodebaseInformation/implementation_plan.md` | Documentation | N/A | LOW | N/A |
| `./.claude/worktrees/agent-a221efa2bcbf5bf06/CodebaseInformation/migration_ledger.md` | Documentation | N/A | LOW | N/A |
| `./.claude/worktrees/agent-a221efa2bcbf5bf06/CodebaseInformation/prompt_features_batch.md` | Documentation | N/A | LOW | N/A |
| `./.claude/worktrees/agent-a221efa2bcbf5bf06/CodebaseInformation/prompt_homescreen_redesign.md` | Documentation | N/A | LOW | N/A |
| `./.claude/worktrees/agent-a221efa2bcbf5bf06/CodebaseInformation/prompt_immersive_chart.md` | Documentation | N/A | LOW | N/A |
| `./.claude/worktrees/agent-a221efa2bcbf5bf06/CodebaseInformation/prompt_launch_animation.md` | Documentation | N/A | LOW | N/A |
| `./.claude/worktrees/agent-a221efa2bcbf5bf06/CodebaseInformation/prompt_mega_ui_overhaul.md` | Documentation | N/A | LOW | N/A |
| `./.claude/worktrees/agent-a221efa2bcbf5bf06/CodebaseInformation/tasks_earnings_feed_calendar.md` | Documentation | N/A | LOW | N/A |
| `./.claude/worktrees/agent-a221efa2bcbf5bf06/CodebaseInformation/tasks_ideas_sprint.md` | Documentation | N/A | LOW | N/A |
| `./.claude/worktrees/agent-a221efa2bcbf5bf06/CodebaseInformation/tasks_market_implementation.md` | Documentation | N/A | LOW | N/A |
| `./.claude/worktrees/agent-a221efa2bcbf5bf06/CodebaseInformation/tasks_notifications_system.md` | Documentation | N/A | LOW | N/A |
| `./.claude/worktrees/agent-a221efa2bcbf5bf06/CodebaseInformation/tasks_performance_fixes.md` | Documentation | N/A | LOW | N/A |
| `./.claude/worktrees/agent-a221efa2bcbf5bf06/CodebaseInformation/tasks_ui_redesign.md` | Documentation | N/A | LOW | N/A |
| `./.claude/worktrees/agent-a221efa2bcbf5bf06/CodebaseInformation/todo_2026_06_04_backend_fixes.md` | Documentation | N/A | LOW | N/A |
| `./.claude/worktrees/agent-a221efa2bcbf5bf06/Nivesh_Backend_AI_Proposal.docx` | Word doc | N/A | LOW | N/A |
| `./.claude/worktrees/agent-a221efa2bcbf5bf06/README.md` | Documentation | N/A | LOW | N/A |
| `./.claude/worktrees/agent-a221efa2bcbf5bf06/TODO/2026-06-08_0223_ui-modernization-and-87-edge-case-fixes.md` | Documentation | N/A | LOW | N/A |
| `./.claude/worktrees/agent-a221efa2bcbf5bf06/TODO/2026-06-08_50-improvements-frontend-backend.md` | Documentation | N/A | LOW | N/A |
| `./.claude/worktrees/agent-a221efa2bcbf5bf06/TODO/PLAN.md` | Documentation | N/A | LOW | N/A |
| `./.claude/worktrees/agent-a221efa2bcbf5bf06/backend/.env.example` | .example file | N/A | CRITICAL | N/A |
| `./.claude/worktrees/agent-a221efa2bcbf5bf06/backend/.fuse_hidden0000000e00000001` |  file | N/A | LOW | N/A |
| `./.claude/worktrees/agent-a221efa2bcbf5bf06/backend/.fuse_hidden0000000e00000002` |  file | N/A | LOW | N/A |
| `./.claude/worktrees/agent-a221efa2bcbf5bf06/backend/.fuse_hidden0000000e00000003` |  file | N/A | LOW | N/A |
| `./.claude/worktrees/agent-a221efa2bcbf5bf06/backend/.gitignore` | Git/cache metadata | N/A | LOW | N/A |
| `./.claude/worktrees/agent-a221efa2bcbf5bf06/backend/AGENT_MAP.md` | Documentation | N/A | LOW | N/A |
| `./.claude/worktrees/agent-a221efa2bcbf5bf06/backend/Dockerfile` | Docker container definition | N/A | LOW | N/A |
| `./.claude/worktrees/agent-a221efa2bcbf5bf06/backend/Indian Market AI Analysis Framework.txt` | Text | N/A | LOW | N/A |
| `./.claude/worktrees/agent-a221efa2bcbf5bf06/backend/Indian Market Behavioral Prompt Engineering.txt` | Text | N/A | LOW | N/A |
| `./.claude/worktrees/agent-a221efa2bcbf5bf06/backend/Indian Stock App Feature Analysis.txt` | Text | N/A | LOW | N/A |
| `./.claude/worktrees/agent-a221efa2bcbf5bf06/backend/Indian Stock App Feature Discovery.md` | Documentation | N/A | LOW | N/A |
| `./.claude/worktrees/agent-a221efa2bcbf5bf06/backend/bugs.md` | Documentation | N/A | LOW | N/A |
| `./.claude/worktrees/agent-a221efa2bcbf5bf06/backend/changes.md` | Documentation | N/A | LOW | N/A |
| `./.claude/worktrees/agent-a221efa2bcbf5bf06/backend/comprehensive_tests_explanation.md` | Documentation | N/A | LOW | N/A |
| `./.claude/worktrees/agent-a221efa2bcbf5bf06/backend/core/__init__.py` | Python module | YES | LOW | tested |
| `./.claude/worktrees/agent-a221efa2bcbf5bf06/backend/core/security.py` | Python module | NO | CRITICAL | untested |
| `./.claude/worktrees/agent-a221efa2bcbf5bf06/backend/data/nse_bse_symbols.json` | JSON/config | N/A | LOW | N/A |
| `./.claude/worktrees/agent-a221efa2bcbf5bf06/backend/database.py` | Python module | YES | CRITICAL | tested |
| `./.claude/worktrees/agent-a221efa2bcbf5bf06/backend/deploy_update.sh` | Shell script | N/A | LOW | N/A |
| `./.claude/worktrees/agent-a221efa2bcbf5bf06/backend/docs/superpowers/plans/2025-05-18-execution-autonomy-resilience.md` | Documentation | N/A | LOW | N/A |
| `./.claude/worktrees/agent-a221efa2bcbf5bf06/backend/docs/superpowers/plans/2025-05-18-polish-imports-readability.md` | Documentation | N/A | LOW | N/A |
| `./.claude/worktrees/agent-a221efa2bcbf5bf06/backend/helpers.py` | Python module | NO | LOW | untested |
| `./.claude/worktrees/agent-a221efa2bcbf5bf06/backend/main.py` | Python module | NO | CRITICAL | untested |
| `./.claude/worktrees/agent-a221efa2bcbf5bf06/backend/main_legacy_backup.py` | Python module | NO | LOW | untested |
| `./.claude/worktrees/agent-a221efa2bcbf5bf06/backend/main_old_monolithic.py` | Python module | NO | LOW | untested |
| `./.claude/worktrees/agent-a221efa2bcbf5bf06/backend/migrate_trade_journal.py` | Python module | NO | LOW | untested |
| `./.claude/worktrees/agent-a221efa2bcbf5bf06/backend/nivesh.service` | .service file | N/A | LOW | N/A |
| `./.claude/worktrees/agent-a221efa2bcbf5bf06/backend/nivesh_app_context.md` | Documentation | N/A | LOW | N/A |
| `./.claude/worktrees/agent-a221efa2bcbf5bf06/backend/populate_portfolio.py` | Python module | NO | LOW | untested |
| `./.claude/worktrees/agent-a221efa2bcbf5bf06/backend/portfolio_charts.py` | Python module | NO | LOW | untested |
| `./.claude/worktrees/agent-a221efa2bcbf5bf06/backend/prompts.py` | Python module | NO | HIGH | untested |
| `./.claude/worktrees/agent-a221efa2bcbf5bf06/backend/requirements.txt` | Python dependencies | N/A | LOW | N/A |
| `./.claude/worktrees/agent-a221efa2bcbf5bf06/backend/routers/__init__.py` | Python module | YES | LOW | tested |
| `./.claude/worktrees/agent-a221efa2bcbf5bf06/backend/routers/alerts.py` | Python module | YES | LOW | tested |
| `./.claude/worktrees/agent-a221efa2bcbf5bf06/backend/routers/analysis.py` | Python module | YES | LOW | tested |
| `./.claude/worktrees/agent-a221efa2bcbf5bf06/backend/routers/auth.py` | Python module | NO | CRITICAL | untested |
| `./.claude/worktrees/agent-a221efa2bcbf5bf06/backend/routers/dashboard.py` | Python module | YES | LOW | tested |
| `./.claude/worktrees/agent-a221efa2bcbf5bf06/backend/routers/market.py` | Python module | YES | LOW | tested |
| `./.claude/worktrees/agent-a221efa2bcbf5bf06/backend/routers/notifications.py` | Python module | NO | LOW | untested |
| `./.claude/worktrees/agent-a221efa2bcbf5bf06/backend/routers/portfolio.py` | Python module | YES | LOW | tested |
| `./.claude/worktrees/agent-a221efa2bcbf5bf06/backend/routers/user.py` | Python module | NO | LOW | untested |
| `./.claude/worktrees/agent-a221efa2bcbf5bf06/backend/run.sh` | Shell script | N/A | LOW | N/A |
| `./.claude/worktrees/agent-a221efa2bcbf5bf06/backend/run_advisor_harvest.py` | Python module | NO | LOW | untested |
| `./.claude/worktrees/agent-a221efa2bcbf5bf06/backend/schemas/__init__.py` | Python module | YES | LOW | tested |
| `./.claude/worktrees/agent-a221efa2bcbf5bf06/backend/schemas/auth.py` | Python module | NO | CRITICAL | untested |
| `./.claude/worktrees/agent-a221efa2bcbf5bf06/backend/schemas/market.py` | Python module | YES | LOW | tested |
| `./.claude/worktrees/agent-a221efa2bcbf5bf06/backend/schemas/portfolio.py` | Python module | YES | LOW | tested |
| `./.claude/worktrees/agent-a221efa2bcbf5bf06/backend/scratch_dividend.py` | Python module | NO | LOW | untested |
| `./.claude/worktrees/agent-a221efa2bcbf5bf06/backend/scratch_item38.py` | Python module | NO | LOW | untested |
| `./.claude/worktrees/agent-a221efa2bcbf5bf06/backend/scratch_item38_router.py` | Python module | NO | LOW | untested |
| `./.claude/worktrees/agent-a221efa2bcbf5bf06/backend/scratch_item39.py` | Python module | NO | LOW | untested |
| `./.claude/worktrees/agent-a221efa2bcbf5bf06/backend/scratch_item49.py` | Python module | NO | LOW | untested |
| `./.claude/worktrees/agent-a221efa2bcbf5bf06/backend/scratch_middleware.py` | Python module | NO | LOW | untested |
| `./.claude/worktrees/agent-a221efa2bcbf5bf06/backend/scripts/cache_cleanup.sh` | Shell script | N/A | LOW | N/A |
| `./.claude/worktrees/agent-a221efa2bcbf5bf06/backend/scripts/refresh_nse_symbols.py` | Python module | NO | LOW | untested |
| `./.claude/worktrees/agent-a221efa2bcbf5bf06/backend/scripts/reset_mock_user.py` | Python module | NO | LOW | untested |
| `./.claude/worktrees/agent-a221efa2bcbf5bf06/backend/services/__init__.py` | Python module | YES | LOW | tested |
| `./.claude/worktrees/agent-a221efa2bcbf5bf06/backend/services/advisor_harvester.py` | Python module | YES | LOW | tested |
| `./.claude/worktrees/agent-a221efa2bcbf5bf06/backend/services/cache_service.py` | Python module | NO | LOW | untested |
| `./.claude/worktrees/agent-a221efa2bcbf5bf06/backend/services/disk_cache.py` | Python module | NO | LOW | untested |
| `./.claude/worktrees/agent-a221efa2bcbf5bf06/backend/services/error_telemetry.py` | Python module | NO | LOW | untested |
| `./.claude/worktrees/agent-a221efa2bcbf5bf06/backend/services/factor_engine.py` | Python module | NO | LOW | untested |
| `./.claude/worktrees/agent-a221efa2bcbf5bf06/backend/services/feedback_injector.py` | Python module | NO | LOW | untested |
| `./.claude/worktrees/agent-a221efa2bcbf5bf06/backend/services/filings_extractor.py` | Python module | NO | LOW | untested |
| `./.claude/worktrees/agent-a221efa2bcbf5bf06/backend/services/harvest_worker.py` | Python module | NO | LOW | untested |
| `./.claude/worktrees/agent-a221efa2bcbf5bf06/backend/services/llm_utils.py` | Python module | YES | LOW | tested |
| `./.claude/worktrees/agent-a221efa2bcbf5bf06/backend/services/news_harvester.py` | Python module | NO | LOW | untested |
| `./.claude/worktrees/agent-a221efa2bcbf5bf06/backend/services/nse_data_provider.py` | Python module | NO | LOW | untested |
| `./.claude/worktrees/agent-a221efa2bcbf5bf06/backend/services/options_scraper.py` | Python module | NO | LOW | untested |
| `./.claude/worktrees/agent-a221efa2bcbf5bf06/backend/services/orchestrator.py` | Python module | NO | LOW | untested |
| `./.claude/worktrees/agent-a221efa2bcbf5bf06/backend/services/piotroski.py` | Python module | NO | LOW | untested |
| `./.claude/worktrees/agent-a221efa2bcbf5bf06/backend/services/pkscreener_runner.py` | Python module | NO | LOW | untested |
| `./.claude/worktrees/agent-a221efa2bcbf5bf06/backend/services/portfolio_snapshot.py` | Python module | NO | LOW | untested |
| `./.claude/worktrees/agent-a221efa2bcbf5bf06/backend/services/scraper.py` | Python module | NO | LOW | untested |
| `./.claude/worktrees/agent-a221efa2bcbf5bf06/backend/services/sentiment_engine.py` | Python module | NO | LOW | untested |
| `./.claude/worktrees/agent-a221efa2bcbf5bf06/backend/services/staleness.py` | Python module | NO | LOW | untested |
| `./.claude/worktrees/agent-a221efa2bcbf5bf06/backend/services/ticker_matcher.py` | Python module | NO | LOW | untested |
| `./.claude/worktrees/agent-a221efa2bcbf5bf06/backend/services/transcript_engine.py` | Python module | NO | LOW | untested |
| `./.claude/worktrees/agent-a221efa2bcbf5bf06/backend/services/youtube_harvester.py` | Python module | YES | LOW | tested |
| `./.claude/worktrees/agent-a221efa2bcbf5bf06/backend/tasks_advisor.md` | Documentation | N/A | LOW | N/A |
| `./.claude/worktrees/agent-a221efa2bcbf5bf06/backend/tasks_api_key_deployment.md` | Documentation | N/A | LOW | N/A |
| `./.claude/worktrees/agent-a221efa2bcbf5bf06/backend/tasks_ensemble.md` | Documentation | N/A | LOW | N/A |
| `./.claude/worktrees/agent-a221efa2bcbf5bf06/backend/tasks_final_refactor.md` | Documentation | N/A | LOW | N/A |
| `./.claude/worktrees/agent-a221efa2bcbf5bf06/backend/telemetry_spec.json` | JSON/config | N/A | LOW | N/A |
| `./.claude/worktrees/agent-a221efa2bcbf5bf06/backend/test_analyze_diagnostic.py` | Test | NO | LOW | untested |
| `./.claude/worktrees/agent-a221efa2bcbf5bf06/backend/test_analyze_uncached.py` | Test | NO | LOW | untested |
| `./.claude/worktrees/agent-a221efa2bcbf5bf06/backend/test_claude.py` | Test | NO | LOW | untested |
| `./.claude/worktrees/agent-a221efa2bcbf5bf06/backend/test_deep_scan.py` | Test | NO | LOW | untested |
| `./.claude/worktrees/agent-a221efa2bcbf5bf06/backend/test_deepseek_claude.py` | Test | NO | LOW | untested |
| `./.claude/worktrees/agent-a221efa2bcbf5bf06/backend/test_new_endpoints.py` | Test | NO | LOW | untested |
| `./.claude/worktrees/agent-a221efa2bcbf5bf06/backend/test_nse.py` | Test | NO | LOW | untested |
| `./.claude/worktrees/agent-a221efa2bcbf5bf06/backend/test_run.py` | Test | NO | LOW | untested |
| `./.claude/worktrees/agent-a221efa2bcbf5bf06/backend/tests/TEST_INVENTORY.md` | Test | N/A | LOW | N/A |
| `./.claude/worktrees/agent-a221efa2bcbf5bf06/backend/tests/conftest.py` | Test fixtures/config | N/A | LOW | N/A |
| `./.claude/worktrees/agent-a221efa2bcbf5bf06/backend/tests/nivesh_api.postman_collection.json` | JSON/config | N/A | LOW | N/A |
| `./.claude/worktrees/agent-a221efa2bcbf5bf06/backend/tests/nivesh_local.postman_environment.json` | JSON/config | N/A | LOW | N/A |
| `./.claude/worktrees/agent-a221efa2bcbf5bf06/backend/tests/nivesh_prod.postman_environment.json` | JSON/config | N/A | LOW | N/A |
| `./.claude/worktrees/agent-a221efa2bcbf5bf06/backend/tests/test_api.py` | Test | N/A | LOW | N/A |
| `./.claude/worktrees/agent-a221efa2bcbf5bf06/backend/tests/test_backend_tasks.py` | Test | N/A | LOW | N/A |
| `./.claude/worktrees/agent-a221efa2bcbf5bf06/backend/tests/test_comprehensive.py` | Test | N/A | LOW | N/A |
| `./.claude/worktrees/agent-a221efa2bcbf5bf06/backend/tests/test_e2e_api.py` | Test | N/A | LOW | N/A |
| `./.claude/worktrees/agent-a221efa2bcbf5bf06/backend/tests/test_model_names.py` | Test | N/A | LOW | N/A |
| `./.claude/worktrees/agent-a221efa2bcbf5bf06/backend/tests_suite/conftest.py` | Test fixtures/config | N/A | LOW | N/A |
| `./.claude/worktrees/agent-a221efa2bcbf5bf06/backend/tests_suite/test_ai_mock_comprehensive.py` | Test | N/A | LOW | N/A |
| `./.claude/worktrees/agent-a221efa2bcbf5bf06/backend/tests_suite/test_api_endpoints_comprehensive.py` | Test | N/A | LOW | N/A |
| `./.claude/worktrees/agent-a221efa2bcbf5bf06/backend/tests_suite/test_database_comprehensive.py` | Test | N/A | LOW | N/A |
| `./.claude/worktrees/agent-a221efa2bcbf5bf06/backend/tests_suite/test_scraper_mock_comprehensive.py` | Test | N/A | LOW | N/A |
| `./.claude/worktrees/agent-a221efa2bcbf5bf06/backend/tests_suite/test_staleness_comprehensive.py` | Test | N/A | LOW | N/A |
| `./.claude/worktrees/agent-a221efa2bcbf5bf06/backend/tests_suite/test_ticker_matcher_comprehensive.py` | Test | N/A | LOW | N/A |
| `./.claude/worktrees/agent-a221efa2bcbf5bf06/backend/update.sh` | Shell script | N/A | LOW | N/A |
| `./.claude/worktrees/agent-a221efa2bcbf5bf06/commit.sh` | Shell script | N/A | LOW | N/A |
| `./.claude/worktrees/agent-a221efa2bcbf5bf06/implementation_plan.md` | Documentation | N/A | LOW | N/A |
| `./.claude/worktrees/agent-a221efa2bcbf5bf06/install-agents.sh` | Shell script | N/A | LOW | N/A |
| `./.claude/worktrees/agent-a221efa2bcbf5bf06/ios/GEMINI.md` | Documentation | N/A | LOW | N/A |
| `./.claude/worktrees/agent-a221efa2bcbf5bf06/ios/HOW_THE_ANALYSIS_WORKS.md` | Documentation | N/A | LOW | N/A |
| `./.claude/worktrees/agent-a221efa2bcbf5bf06/ios/NIVESH_FULL_CONTEXT.md` | Documentation | N/A | LOW | N/A |
| `./.claude/worktrees/agent-a221efa2bcbf5bf06/ios/StockApp/AnalysisScreen.swift` | Swift source | N/A | LOW | N/A |
| `./.claude/worktrees/agent-a221efa2bcbf5bf06/ios/StockApp/Components.swift` | Swift source | N/A | LOW | N/A |
| `./.claude/worktrees/agent-a221efa2bcbf5bf06/ios/StockApp/ContentView.swift` | Swift source | N/A | HIGH | N/A |
| `./.claude/worktrees/agent-a221efa2bcbf5bf06/ios/StockApp/Formatters.swift` | Swift source | N/A | LOW | N/A |
| `./.claude/worktrees/agent-a221efa2bcbf5bf06/ios/StockApp/HomeScreen.swift` | Swift source | N/A | LOW | N/A |
| `./.claude/worktrees/agent-a221efa2bcbf5bf06/ios/StockApp/Models.swift` | Swift source | N/A | LOW | N/A |
| `./.claude/worktrees/agent-a221efa2bcbf5bf06/ios/StockApp/NetworkManager.swift` | Swift source | N/A | HIGH | N/A |
| `./.claude/worktrees/agent-a221efa2bcbf5bf06/ios/StockApp/SearchScreen.swift` | Swift source | N/A | LOW | N/A |
| `./.claude/worktrees/agent-a221efa2bcbf5bf06/ios/StockApp/StockAppApp.swift` | Swift source | N/A | LOW | N/A |
| `./.claude/worktrees/agent-a221efa2bcbf5bf06/ios/StockApp/StockDatabase.swift` | Swift source | N/A | HIGH | N/A |
| `./.claude/worktrees/agent-a221efa2bcbf5bf06/ios/StockApp/WatchlistScreen.swift` | Swift source | N/A | LOW | N/A |
| `./.claude/worktrees/agent-a221efa2bcbf5bf06/ios/StockApp/WatchlistStore.swift` | Swift source | N/A | LOW | N/A |
| `./.claude/worktrees/agent-a221efa2bcbf5bf06/ios/StockApp/stockme/Info.plist` | Plist | N/A | LOW | N/A |
| `./.claude/worktrees/agent-a221efa2bcbf5bf06/ios/StockApp/stockme/LaunchScreen.storyboard` | Storyboard | N/A | LOW | N/A |
| `./.claude/worktrees/agent-a221efa2bcbf5bf06/ios/StockApp/stockme/NiveshWidget/Info.plist` | Plist | N/A | LOW | N/A |
| `./.claude/worktrees/agent-a221efa2bcbf5bf06/ios/StockApp/stockme/NiveshWidget/NiveshWidget.swift` | Swift source | N/A | LOW | N/A |
| `./.claude/worktrees/agent-a221efa2bcbf5bf06/ios/StockApp/stockme/add_frameworks.rb` | Ruby script | N/A | LOW | N/A |
| `./.claude/worktrees/agent-a221efa2bcbf5bf06/ios/StockApp/stockme/add_shared.rb` | Ruby script | N/A | LOW | N/A |
| `./.claude/worktrees/agent-a221efa2bcbf5bf06/ios/StockApp/stockme/add_target.rb` | Ruby script | N/A | LOW | N/A |
| `./.claude/worktrees/agent-a221efa2bcbf5bf06/ios/StockApp/stockme/dump.rb` | Ruby script | N/A | LOW | N/A |
| `./.claude/worktrees/agent-a221efa2bcbf5bf06/ios/StockApp/stockme/fix_files.rb` | Ruby script | N/A | LOW | N/A |
| `./.claude/worktrees/agent-a221efa2bcbf5bf06/ios/StockApp/stockme/fix_product_name.rb` | Ruby script | N/A | LOW | N/A |
| `./.claude/worktrees/agent-a221efa2bcbf5bf06/ios/StockApp/stockme/launch_animated.mp4` | Video | N/A | LOW | N/A |
| `./.claude/worktrees/agent-a221efa2bcbf5bf06/ios/StockApp/stockme/list_files.rb` | Ruby script | N/A | LOW | N/A |
| `./.claude/worktrees/agent-a221efa2bcbf5bf06/ios/StockApp/stockme/remove_ext.rb` | Ruby script | N/A | LOW | N/A |
| `./.claude/worktrees/agent-a221efa2bcbf5bf06/ios/StockApp/stockme/remove_haptic.rb` | Ruby script | N/A | LOW | N/A |
| `./.claude/worktrees/agent-a221efa2bcbf5bf06/ios/StockApp/stockme/stockme.xcodeproj/project.pbxproj` | Xcode project data | N/A | LOW | N/A |
| `./.claude/worktrees/agent-a221efa2bcbf5bf06/ios/StockApp/stockme/stockme.xcodeproj/project.xcworkspace/contents.xcworkspacedata` | .xcworkspacedata file | N/A | LOW | N/A |
| `./.claude/worktrees/agent-a221efa2bcbf5bf06/ios/StockApp/stockme/stockme.xcodeproj/xcshareddata/xcschemes/NiveshWidgetExtension.xcscheme` | .xcscheme file | N/A | LOW | N/A |
| `./.claude/worktrees/agent-a221efa2bcbf5bf06/ios/StockApp/stockme/stockme.xcodeproj/xcshareddata/xcschemes/stockme.xcscheme` | .xcscheme file | N/A | LOW | N/A |
| `./.claude/worktrees/agent-a221efa2bcbf5bf06/ios/StockApp/stockme/stockme/AppDelegate.swift` | Swift source | N/A | LOW | N/A |
| `./.claude/worktrees/agent-a221efa2bcbf5bf06/ios/StockApp/stockme/stockme/AppSoundManager.swift` | Swift source | N/A | LOW | N/A |
| `./.claude/worktrees/agent-a221efa2bcbf5bf06/ios/StockApp/stockme/stockme/Assets.xcassets/AccentColor.colorset/Contents.json` | JSON/config | N/A | LOW | N/A |
| `./.claude/worktrees/agent-a221efa2bcbf5bf06/ios/StockApp/stockme/stockme/Assets.xcassets/AppIcon.appiconset/Contents.json` | JSON/config | N/A | LOW | N/A |
| `./.claude/worktrees/agent-a221efa2bcbf5bf06/ios/StockApp/stockme/stockme/Assets.xcassets/AppIcon.appiconset/Icon-1024.png` | Image | N/A | LOW | N/A |
| `./.claude/worktrees/agent-a221efa2bcbf5bf06/ios/StockApp/stockme/stockme/Assets.xcassets/AppIcon.appiconset/Icon-120.png` | Image | N/A | LOW | N/A |
| `./.claude/worktrees/agent-a221efa2bcbf5bf06/ios/StockApp/stockme/stockme/Assets.xcassets/AppIcon.appiconset/Icon-152.png` | Image | N/A | LOW | N/A |
| `./.claude/worktrees/agent-a221efa2bcbf5bf06/ios/StockApp/stockme/stockme/Assets.xcassets/AppIcon.appiconset/Icon-167.png` | Image | N/A | LOW | N/A |
| `./.claude/worktrees/agent-a221efa2bcbf5bf06/ios/StockApp/stockme/stockme/Assets.xcassets/AppIcon.appiconset/Icon-180.png` | Image | N/A | LOW | N/A |
| `./.claude/worktrees/agent-a221efa2bcbf5bf06/ios/StockApp/stockme/stockme/Assets.xcassets/AppIcon.appiconset/Icon-20.png` | Image | N/A | LOW | N/A |
| `./.claude/worktrees/agent-a221efa2bcbf5bf06/ios/StockApp/stockme/stockme/Assets.xcassets/AppIcon.appiconset/Icon-29.png` | Image | N/A | LOW | N/A |
| `./.claude/worktrees/agent-a221efa2bcbf5bf06/ios/StockApp/stockme/stockme/Assets.xcassets/AppIcon.appiconset/Icon-40.png` | Image | N/A | LOW | N/A |
| `./.claude/worktrees/agent-a221efa2bcbf5bf06/ios/StockApp/stockme/stockme/Assets.xcassets/AppIcon.appiconset/Icon-58.png` | Image | N/A | LOW | N/A |
| `./.claude/worktrees/agent-a221efa2bcbf5bf06/ios/StockApp/stockme/stockme/Assets.xcassets/AppIcon.appiconset/Icon-60.png` | Image | N/A | LOW | N/A |
| `./.claude/worktrees/agent-a221efa2bcbf5bf06/ios/StockApp/stockme/stockme/Assets.xcassets/AppIcon.appiconset/Icon-76.png` | Image | N/A | LOW | N/A |
| `./.claude/worktrees/agent-a221efa2bcbf5bf06/ios/StockApp/stockme/stockme/Assets.xcassets/AppIcon.appiconset/Icon-80.png` | Image | N/A | LOW | N/A |
| `./.claude/worktrees/agent-a221efa2bcbf5bf06/ios/StockApp/stockme/stockme/Assets.xcassets/AppIcon.appiconset/Icon-87.png` | Image | N/A | LOW | N/A |
| `./.claude/worktrees/agent-a221efa2bcbf5bf06/ios/StockApp/stockme/stockme/Assets.xcassets/Contents.json` | JSON/config | N/A | LOW | N/A |
| `./.claude/worktrees/agent-a221efa2bcbf5bf06/ios/StockApp/stockme/stockme/AuthManager.swift` | Swift source | N/A | HIGH | N/A |
| `./.claude/worktrees/agent-a221efa2bcbf5bf06/ios/StockApp/stockme/stockme/BanknoteDesignSystem.swift` | Swift source | N/A | HIGH | N/A |
| `./.claude/worktrees/agent-a221efa2bcbf5bf06/ios/StockApp/stockme/stockme/Charts/ImmersivePortfolioHeroChart.swift` | Swift source | N/A | LOW | N/A |
| `./.claude/worktrees/agent-a221efa2bcbf5bf06/ios/StockApp/stockme/stockme/Charts/StockCharts.swift` | Swift source | N/A | HIGH | N/A |
| `./.claude/worktrees/agent-a221efa2bcbf5bf06/ios/StockApp/stockme/stockme/Components/AdvisorBioCard.swift` | Swift source | N/A | LOW | N/A |
| `./.claude/worktrees/agent-a221efa2bcbf5bf06/ios/StockApp/stockme/stockme/Components/BanknoteErrorCanvas.swift` | Swift source | N/A | LOW | N/A |
| `./.claude/worktrees/agent-a221efa2bcbf5bf06/ios/StockApp/stockme/stockme/Components/DialecticProgressView.swift` | Swift source | N/A | LOW | N/A |
| `./.claude/worktrees/agent-a221efa2bcbf5bf06/ios/StockApp/stockme/stockme/Components/NewsCardView.swift` | Swift source | N/A | LOW | N/A |
| `./.claude/worktrees/agent-a221efa2bcbf5bf06/ios/StockApp/stockme/stockme/Components/SharedComponents.swift` | Swift source | N/A | LOW | N/A |
| `./.claude/worktrees/agent-a221efa2bcbf5bf06/ios/StockApp/stockme/stockme/Components/SharedDarkComponents.swift` | Swift source | N/A | LOW | N/A |
| `./.claude/worktrees/agent-a221efa2bcbf5bf06/ios/StockApp/stockme/stockme/Components/SignalBadgeView.swift` | Swift source | N/A | LOW | N/A |
| `./.claude/worktrees/agent-a221efa2bcbf5bf06/ios/StockApp/stockme/stockme/Components/YouTubeCardView.swift` | Swift source | N/A | LOW | N/A |
| `./.claude/worktrees/agent-a221efa2bcbf5bf06/ios/StockApp/stockme/stockme/ContentView.swift` | Swift source | N/A | HIGH | N/A |
| `./.claude/worktrees/agent-a221efa2bcbf5bf06/ios/StockApp/stockme/stockme/DenominationBackground.swift` | Swift source | N/A | LOW | N/A |
| `./.claude/worktrees/agent-a221efa2bcbf5bf06/ios/StockApp/stockme/stockme/HomeFeedModels.swift` | Swift source | N/A | HIGH | N/A |
| `./.claude/worktrees/agent-a221efa2bcbf5bf06/ios/StockApp/stockme/stockme/HomeFeedService.swift` | Swift source | N/A | HIGH | N/A |
| `./.claude/worktrees/agent-a221efa2bcbf5bf06/ios/StockApp/stockme/stockme/HomeFeedViewModel.swift` | Swift source | N/A | HIGH | N/A |
| `./.claude/worktrees/agent-a221efa2bcbf5bf06/ios/StockApp/stockme/stockme/LaunchSequenceView.swift` | Swift source | N/A | HIGH | N/A |
| `./.claude/worktrees/agent-a221efa2bcbf5bf06/ios/StockApp/stockme/stockme/Models.swift` | Swift source | N/A | LOW | N/A |
| `./.claude/worktrees/agent-a221efa2bcbf5bf06/ios/StockApp/stockme/stockme/NetworkManager+Sidebar.swift` | Swift source | N/A | LOW | N/A |
| `./.claude/worktrees/agent-a221efa2bcbf5bf06/ios/StockApp/stockme/stockme/NetworkManager.swift` | Swift source | N/A | HIGH | N/A |
| `./.claude/worktrees/agent-a221efa2bcbf5bf06/ios/StockApp/stockme/stockme/NotificationManager.swift` | Swift source | N/A | HIGH | N/A |
| `./.claude/worktrees/agent-a221efa2bcbf5bf06/ios/StockApp/stockme/stockme/StockDatabase.swift` | Swift source | N/A | HIGH | N/A |
| `./.claude/worktrees/agent-a221efa2bcbf5bf06/ios/StockApp/stockme/stockme/StockProfileViewModel.swift` | Swift source | N/A | HIGH | N/A |
| `./.claude/worktrees/agent-a221efa2bcbf5bf06/ios/StockApp/stockme/stockme/Utilities/ErrorDiagnoser.swift` | Swift source | N/A | LOW | N/A |
| `./.claude/worktrees/agent-a221efa2bcbf5bf06/ios/StockApp/stockme/stockme/Utilities/Extensions.swift` | Swift source | N/A | HIGH | N/A |
| `./.claude/worktrees/agent-a221efa2bcbf5bf06/ios/StockApp/stockme/stockme/Utilities/FinanceTerms.swift` | Swift source | N/A | LOW | N/A |
| `./.claude/worktrees/agent-a221efa2bcbf5bf06/ios/StockApp/stockme/stockme/Utilities/HapticManager.swift` | Swift source | N/A | HIGH | N/A |
| `./.claude/worktrees/agent-a221efa2bcbf5bf06/ios/StockApp/stockme/stockme/Utilities/IndianFormatter.swift` | Swift source | N/A | HIGH | N/A |
| `./.claude/worktrees/agent-a221efa2bcbf5bf06/ios/StockApp/stockme/stockme/Utilities/TermDefinitionOverlay.swift` | Swift source | N/A | LOW | N/A |
| `./.claude/worktrees/agent-a221efa2bcbf5bf06/ios/StockApp/stockme/stockme/Utilities/Theme.swift` | Swift source | N/A | HIGH | N/A |
| `./.claude/worktrees/agent-a221efa2bcbf5bf06/ios/StockApp/stockme/stockme/Utilities/ThemeManager.swift` | Swift source | N/A | LOW | N/A |
| `./.claude/worktrees/agent-a221efa2bcbf5bf06/ios/StockApp/stockme/stockme/Utilities/TutorialManager.swift` | Swift source | N/A | LOW | N/A |
| `./.claude/worktrees/agent-a221efa2bcbf5bf06/ios/StockApp/stockme/stockme/ValuationCalendarService.swift` | Swift source | N/A | HIGH | N/A |
| `./.claude/worktrees/agent-a221efa2bcbf5bf06/ios/StockApp/stockme/stockme/Views/AdvisoryMatrixCard.swift` | Swift source | N/A | LOW | N/A |
| `./.claude/worktrees/agent-a221efa2bcbf5bf06/ios/StockApp/stockme/stockme/Views/AlertsScreen.swift` | Swift source | N/A | LOW | N/A |
| `./.claude/worktrees/agent-a221efa2bcbf5bf06/ios/StockApp/stockme/stockme/Views/AnalysisHistoryScreen.swift` | Swift source | N/A | LOW | N/A |
| `./.claude/worktrees/agent-a221efa2bcbf5bf06/ios/StockApp/stockme/stockme/Views/AnalysisScreen.swift` | Swift source | N/A | LOW | N/A |
| `./.claude/worktrees/agent-a221efa2bcbf5bf06/ios/StockApp/stockme/stockme/Views/CompareScreen.swift` | Swift source | N/A | LOW | N/A |
| `./.claude/worktrees/agent-a221efa2bcbf5bf06/ios/StockApp/stockme/stockme/Views/DalalStreetConsensusCard.swift` | Swift source | N/A | LOW | N/A |
| `./.claude/worktrees/agent-a221efa2bcbf5bf06/ios/StockApp/stockme/stockme/Views/DisclaimerScreen.swift` | Swift source | N/A | LOW | N/A |
| `./.claude/worktrees/agent-a221efa2bcbf5bf06/ios/StockApp/stockme/stockme/Views/EarningsDashboardView.swift` | Swift source | N/A | LOW | N/A |
| `./.claude/worktrees/agent-a221efa2bcbf5bf06/ios/StockApp/stockme/stockme/Views/ExpertNetworkView.swift` | Swift source | N/A | LOW | N/A |
| `./.claude/worktrees/agent-a221efa2bcbf5bf06/ios/StockApp/stockme/stockme/Views/HistoryScreen.swift` | Swift source | N/A | LOW | N/A |
| `./.claude/worktrees/agent-a221efa2bcbf5bf06/ios/StockApp/stockme/stockme/Views/HomeScreen.swift` | Swift source | N/A | LOW | N/A |
| `./.claude/worktrees/agent-a221efa2bcbf5bf06/ios/StockApp/stockme/stockme/Views/LaunchScreenView.swift` | Swift source | N/A | LOW | N/A |
| `./.claude/worktrees/agent-a221efa2bcbf5bf06/ios/StockApp/stockme/stockme/Views/LoginScreen.swift` | Swift source | N/A | LOW | N/A |
| `./.claude/worktrees/agent-a221efa2bcbf5bf06/ios/StockApp/stockme/stockme/Views/NewsMultimediaView.swift` | Swift source | N/A | LOW | N/A |
| `./.claude/worktrees/agent-a221efa2bcbf5bf06/ios/StockApp/stockme/stockme/Views/NiveshNavigationSidebar.swift` | Swift source | N/A | LOW | N/A |
| `./.claude/worktrees/agent-a221efa2bcbf5bf06/ios/StockApp/stockme/stockme/Views/OnboardingScreen.swift` | Swift source | N/A | LOW | N/A |
| `./.claude/worktrees/agent-a221efa2bcbf5bf06/ios/StockApp/stockme/stockme/Views/PortfolioScreen.swift` | Swift source | N/A | LOW | N/A |
| `./.claude/worktrees/agent-a221efa2bcbf5bf06/ios/StockApp/stockme/stockme/Views/PreIPOMarketplaceView.swift` | Swift source | N/A | LOW | N/A |
| `./.claude/worktrees/agent-a221efa2bcbf5bf06/ios/StockApp/stockme/stockme/Views/SearchScreen.swift` | Swift source | N/A | LOW | N/A |
| `./.claude/worktrees/agent-a221efa2bcbf5bf06/ios/StockApp/stockme/stockme/Views/SettingsScreen.swift` | Swift source | N/A | LOW | N/A |
| `./.claude/worktrees/agent-a221efa2bcbf5bf06/ios/StockApp/stockme/stockme/Views/StockProfileView.swift` | Swift source | N/A | LOW | N/A |
| `./.claude/worktrees/agent-a221efa2bcbf5bf06/ios/StockApp/stockme/stockme/Views/TechnicalMomentumView.swift` | Swift source | N/A | LOW | N/A |
| `./.claude/worktrees/agent-a221efa2bcbf5bf06/ios/StockApp/stockme/stockme/Views/TradeJournalScreen.swift` | Swift source | N/A | LOW | N/A |
| `./.claude/worktrees/agent-a221efa2bcbf5bf06/ios/StockApp/stockme/stockme/Views/TutorialOverlayView.swift` | Swift source | N/A | LOW | N/A |
| `./.claude/worktrees/agent-a221efa2bcbf5bf06/ios/StockApp/stockme/stockme/Views/ValuationCalendarView.swift` | Swift source | N/A | LOW | N/A |
| `./.claude/worktrees/agent-a221efa2bcbf5bf06/ios/StockApp/stockme/stockme/WatchlistScreen.swift` | Swift source | N/A | LOW | N/A |
| `./.claude/worktrees/agent-a221efa2bcbf5bf06/ios/StockApp/stockme/stockme/nivesh_ios_icon.svg` | Vector | N/A | LOW | N/A |
| `./.claude/worktrees/agent-a221efa2bcbf5bf06/ios/StockApp/stockme/stockme/stockmeApp.swift` | Swift source | N/A | HIGH | N/A |
| `./.claude/worktrees/agent-a221efa2bcbf5bf06/ios/StockApp/stockme/stockmeTests/stockmeTests.swift` | Swift source | N/A | LOW | N/A |
| `./.claude/worktrees/agent-a221efa2bcbf5bf06/ios/StockApp/stockme/stockmeUITests/stockmeUITests.swift` | Swift source | N/A | LOW | N/A |
| `./.claude/worktrees/agent-a221efa2bcbf5bf06/ios/StockApp/stockme/stockmeUITests/stockmeUITestsLaunchTests.swift` | Swift source | N/A | LOW | N/A |
| `./.claude/worktrees/agent-a221efa2bcbf5bf06/ios/backend_nivesh_context.md` | Documentation | N/A | LOW | N/A |
| `./.claude/worktrees/agent-a221efa2bcbf5bf06/ios/docs/superpowers/plans/2026-06-02-backend-upgrades-and-features-16-19.md` | Documentation | N/A | LOW | N/A |
| `./.claude/worktrees/agent-a221efa2bcbf5bf06/ios/docs/superpowers/plans/2026-06-02-market-data-and-news-reader.md` | Documentation | N/A | LOW | N/A |
| `./.claude/worktrees/agent-a221efa2bcbf5bf06/ios/docs/superpowers/specs/2026-06-02-market-data-and-news-reader-design.md` | Documentation | N/A | LOW | N/A |
| `./.claude/worktrees/agent-a221efa2bcbf5bf06/ios/frontend_nivesh_context.md` | Documentation | N/A | LOW | N/A |
| `./.claude/worktrees/agent-a221efa2bcbf5bf06/ios/generate_icons.py` | Python module | NO | LOW | untested |
| `./.claude/worktrees/agent-a221efa2bcbf5bf06/ios/main_copy.py` | Python module | NO | LOW | untested |
| `./.claude/worktrees/agent-a221efa2bcbf5bf06/ios/optimized_blocks.py` | Python module | NO | LOW | untested |
| `./.claude/worktrees/agent-a221efa2bcbf5bf06/ios/scraper_copy.py` | Python module | NO | LOW | untested |
| `./.claude/worktrees/agent-a221efa2bcbf5bf06/ios/test_yf_news.py` | Test | NO | LOW | untested |
| `./.claude/worktrees/agent-a221efa2bcbf5bf06/ios/update_main_surgically.py` | Python module | NO | LOW | untested |
| `./.claude/worktrees/agent-a221efa2bcbf5bf06/ios/update_main_surgically_v2.py` | Python module | NO | LOW | untested |
| `./.claude/worktrees/agent-a221efa2bcbf5bf06/ios/update_main_surgically_v3.py` | Python module | NO | LOW | untested |
| `./.claude/worktrees/agent-a221efa2bcbf5bf06/stockme/StockDatabase.swift` | Swift source | N/A | HIGH | N/A |
| `./.claude/worktrees/agent-a221efa2bcbf5bf06/update_maps.py` | Python module | NO | LOW | untested |
## Claude Config

| File | Purpose | Tests | Risk | Status |
|------|---------|-------|------|--------|
| `./.claude/settings.local.json` | JSON/config | N/A | LOW | N/A |
## Agent Skills (Global)

| File | Purpose | Tests | Risk | Status |
|------|---------|-------|------|--------|
| `./.agents/skills/gitnexus/gitnexus-cli/SKILL.md` | Skill | N/A | LOW | N/A |
| `./.agents/skills/gitnexus/gitnexus-debugging/SKILL.md` | Skill | N/A | LOW | N/A |
| `./.agents/skills/gitnexus/gitnexus-exploring/SKILL.md` | Skill | N/A | LOW | N/A |
| `./.agents/skills/gitnexus/gitnexus-guide/SKILL.md` | Skill | N/A | LOW | N/A |
| `./.agents/skills/gitnexus/gitnexus-impact-analysis/SKILL.md` | Skill | N/A | LOW | N/A |
| `./.agents/skills/gitnexus/gitnexus-refactoring/SKILL.md` | Skill | N/A | LOW | N/A |
| `./.agents/skills/graphify/.graphify_version` | Skill | N/A | LOW | N/A |
| `./.agents/skills/graphify/SKILL.md` | Skill | N/A | LOW | N/A |
| `./.agents/skills/graphify/references/add-watch.md` | Skill | N/A | LOW | N/A |
| `./.agents/skills/graphify/references/exports.md` | Skill | N/A | LOW | N/A |
| `./.agents/skills/graphify/references/extraction-spec.md` | Skill | N/A | LOW | N/A |
| `./.agents/skills/graphify/references/github-and-merge.md` | Skill | N/A | LOW | N/A |
| `./.agents/skills/graphify/references/hooks.md` | Skill | N/A | LOW | N/A |
| `./.agents/skills/graphify/references/query.md` | Skill | N/A | LOW | N/A |
| `./.agents/skills/graphify/references/transcribe.md` | Skill | N/A | LOW | N/A |
| `./.agents/skills/graphify/references/update.md` | Skill | N/A | LOW | N/A |
| `./.agents/skills/speckit-agent-context-update/SKILL.md` | Skill | N/A | LOW | N/A |
| `./.agents/skills/speckit-analyze/SKILL.md` | Skill | N/A | LOW | N/A |
| `./.agents/skills/speckit-checklist/SKILL.md` | Skill | N/A | LOW | N/A |
| `./.agents/skills/speckit-clarify/SKILL.md` | Skill | N/A | LOW | N/A |
| `./.agents/skills/speckit-constitution/SKILL.md` | Skill | N/A | LOW | N/A |
| `./.agents/skills/speckit-implement/SKILL.md` | Skill | N/A | LOW | N/A |
| `./.agents/skills/speckit-plan/SKILL.md` | Skill | N/A | LOW | N/A |
| `./.agents/skills/speckit-specify/SKILL.md` | Skill | N/A | LOW | N/A |
| `./.agents/skills/speckit-tasks/SKILL.md` | Skill | N/A | LOW | N/A |
| `./.agents/skills/speckit-taskstoissues/SKILL.md` | Skill | N/A | LOW | N/A |
| `./.agents/skills/ui-ux-pro-max/SKILL.md` | Skill | N/A | LOW | N/A |
| `./.agents/skills/ui-ux-pro-max/data/charts.csv` | Skill | N/A | LOW | N/A |
| `./.agents/skills/ui-ux-pro-max/data/colors.csv` | Skill | N/A | LOW | N/A |
| `./.agents/skills/ui-ux-pro-max/data/icons.csv` | Skill | N/A | LOW | N/A |
| `./.agents/skills/ui-ux-pro-max/data/landing.csv` | Skill | N/A | LOW | N/A |
| `./.agents/skills/ui-ux-pro-max/data/products.csv` | Skill | N/A | LOW | N/A |
| `./.agents/skills/ui-ux-pro-max/data/react-performance.csv` | Skill | N/A | LOW | N/A |
| `./.agents/skills/ui-ux-pro-max/data/stacks/astro.csv` | Skill | N/A | LOW | N/A |
| `./.agents/skills/ui-ux-pro-max/data/stacks/flutter.csv` | Skill | N/A | LOW | N/A |
| `./.agents/skills/ui-ux-pro-max/data/stacks/html-tailwind.csv` | Skill | N/A | LOW | N/A |
| `./.agents/skills/ui-ux-pro-max/data/stacks/jetpack-compose.csv` | Skill | N/A | LOW | N/A |
| `./.agents/skills/ui-ux-pro-max/data/stacks/nextjs.csv` | Skill | N/A | LOW | N/A |
| `./.agents/skills/ui-ux-pro-max/data/stacks/nuxt-ui.csv` | Skill | N/A | LOW | N/A |
| `./.agents/skills/ui-ux-pro-max/data/stacks/nuxtjs.csv` | Skill | N/A | LOW | N/A |
| `./.agents/skills/ui-ux-pro-max/data/stacks/react-native.csv` | Skill | N/A | LOW | N/A |
| `./.agents/skills/ui-ux-pro-max/data/stacks/react.csv` | Skill | N/A | LOW | N/A |
| `./.agents/skills/ui-ux-pro-max/data/stacks/shadcn.csv` | Skill | N/A | LOW | N/A |
| `./.agents/skills/ui-ux-pro-max/data/stacks/svelte.csv` | Skill | N/A | LOW | N/A |
| `./.agents/skills/ui-ux-pro-max/data/stacks/swiftui.csv` | Skill | N/A | LOW | N/A |
| `./.agents/skills/ui-ux-pro-max/data/stacks/vue.csv` | Skill | N/A | LOW | N/A |
| `./.agents/skills/ui-ux-pro-max/data/styles.csv` | Skill | N/A | LOW | N/A |
| `./.agents/skills/ui-ux-pro-max/data/typography.csv` | Skill | N/A | LOW | N/A |
| `./.agents/skills/ui-ux-pro-max/data/ui-reasoning.csv` | Skill | N/A | LOW | N/A |
| `./.agents/skills/ui-ux-pro-max/data/ux-guidelines.csv` | Skill | N/A | LOW | N/A |
| `./.agents/skills/ui-ux-pro-max/data/web-interface.csv` | Skill | N/A | LOW | N/A |
| `./.agents/skills/ui-ux-pro-max/scripts/core.py` | Skill | NO | LOW | untested |
| `./.agents/skills/ui-ux-pro-max/scripts/design_system.py` | Skill | NO | LOW | untested |
| `./.agents/skills/ui-ux-pro-max/scripts/search.py` | Skill | NO | LOW | untested |
## Agent Sentinel

| File | Purpose | Tests | Risk | Status |
|------|---------|-------|------|--------|
| `./.agents/sentinel/BRIEFING.md` | Documentation | N/A | LOW | N/A |
| `./.agents/sentinel/handoff.md` | Documentation | N/A | LOW | N/A |
## Agent Config

| File | Purpose | Tests | Risk | Status |
|------|---------|-------|------|--------|
| `./.agents/ORIGINAL_REQUEST.md` | Documentation | N/A | LOW | N/A |
## Superpowers State

| File | Purpose | Tests | Risk | Status |
|------|---------|-------|------|--------|
| `./.superpowers/brainstorm/38554-1781616268/content/ai-engine-dashboard-terminal-v2.html` | Superpowers | N/A | LOW | N/A |
| `./.superpowers/brainstorm/38554-1781616268/content/ai-engine-dashboard-v1.html` | Superpowers | N/A | LOW | N/A |
| `./.superpowers/brainstorm/38554-1781616268/state/events` | Superpowers | N/A | LOW | N/A |
| `./.superpowers/brainstorm/38554-1781616268/state/server-info` | Superpowers | N/A | LOW | N/A |
| `./.superpowers/brainstorm/38554-1781616268/state/server.pid` | Superpowers | N/A | LOW | N/A |
## GitNexus Index

| File | Purpose | Tests | Risk | Status |
|------|---------|-------|------|--------|
| `./.gitnexus/.gitignore` | Git/cache metadata | N/A | LOW | N/A |
| `./.gitnexus/lbug` | GitNexus | N/A | LOW | N/A |
| `./.gitnexus/meta.json` | GitNexus | N/A | LOW | N/A |
| `./.gitnexus/parse-cache/0a93894b445f3642fa0d5ba84bd5cd14ca1c933126f91524abeb6ed90554e6d3.json` | GitNexus | N/A | LOW | N/A |
| `./.gitnexus/parse-cache/38398904e8163bec3beddb421e5a9048e700de2704fcb79e7b84df08b48a2cc5.json` | GitNexus | N/A | LOW | N/A |
| `./.gitnexus/parse-cache/c1cba7c0cdc7788b8470aba1111ea37dee2770f70459a1d80d6e8766caa39141.json` | GitNexus | N/A | LOW | N/A |
| `./.gitnexus/parse-cache/index.json` | GitNexus | N/A | LOW | N/A |
## Remember (Memory System)

| File | Purpose | Tests | Risk | Status |
|------|---------|-------|------|--------|
| `./.remember/.gitignore` | Git/cache metadata | N/A | LOW | N/A |
| `./.remember/archive.md` | Memory log | N/A | LOW | N/A |
| `./.remember/logs/autonomous/save-064124.log` | Memory log | N/A | LOW | N/A |
| `./.remember/logs/autonomous/save-064127.log` | Memory log | N/A | LOW | N/A |
| `./.remember/logs/autonomous/save-215205.log` | Memory log | N/A | LOW | N/A |
| `./.remember/logs/autonomous/save-215206.log` | Memory log | N/A | LOW | N/A |
| `./.remember/logs/autonomous/save-215216.log` | Memory log | N/A | LOW | N/A |
| `./.remember/logs/autonomous/save-215236.log` | Memory log | N/A | LOW | N/A |
| `./.remember/logs/autonomous/save-215257.log` | Memory log | N/A | LOW | N/A |
| `./.remember/logs/autonomous/save-215330.log` | Memory log | N/A | LOW | N/A |
| `./.remember/logs/autonomous/save-215340.log` | Memory log | N/A | LOW | N/A |
| `./.remember/logs/autonomous/save-215347.log` | Memory log | N/A | LOW | N/A |
| `./.remember/logs/autonomous/save-215353.log` | Memory log | N/A | LOW | N/A |
| `./.remember/logs/autonomous/save-215358.log` | Memory log | N/A | LOW | N/A |
| `./.remember/logs/autonomous/save-215403.log` | Memory log | N/A | LOW | N/A |
| `./.remember/logs/autonomous/save-215411.log` | Memory log | N/A | LOW | N/A |
| `./.remember/logs/autonomous/save-215439.log` | Memory log | N/A | LOW | N/A |
| `./.remember/logs/autonomous/save-215503.log` | Memory log | N/A | LOW | N/A |
| `./.remember/logs/autonomous/save-215515.log` | Memory log | N/A | LOW | N/A |
| `./.remember/logs/autonomous/save-215524.log` | Memory log | N/A | LOW | N/A |
| `./.remember/logs/autonomous/save-215530.log` | Memory log | N/A | LOW | N/A |
| `./.remember/logs/autonomous/save-215539.log` | Memory log | N/A | LOW | N/A |
| `./.remember/logs/autonomous/save-220016.log` | Memory log | N/A | LOW | N/A |
| `./.remember/logs/autonomous/save-220020.log` | Memory log | N/A | LOW | N/A |
| `./.remember/logs/autonomous/save-220021.log` | Memory log | N/A | LOW | N/A |
| `./.remember/logs/autonomous/save-220026.log` | Memory log | N/A | LOW | N/A |
| `./.remember/logs/autonomous/save-220034.log` | Memory log | N/A | LOW | N/A |
| `./.remember/logs/autonomous/save-220038.log` | Memory log | N/A | LOW | N/A |
| `./.remember/logs/autonomous/save-220043.log` | Memory log | N/A | LOW | N/A |
| `./.remember/logs/autonomous/save-220047.log` | Memory log | N/A | LOW | N/A |
| `./.remember/logs/autonomous/save-220052.log` | Memory log | N/A | LOW | N/A |
| `./.remember/logs/autonomous/save-220058.log` | Memory log | N/A | LOW | N/A |
| `./.remember/logs/autonomous/save-220104.log` | Memory log | N/A | LOW | N/A |
| `./.remember/logs/autonomous/save-220108.log` | Memory log | N/A | LOW | N/A |
| `./.remember/logs/autonomous/save-220112.log` | Memory log | N/A | LOW | N/A |
| `./.remember/logs/autonomous/save-220116.log` | Memory log | N/A | LOW | N/A |
| `./.remember/logs/autonomous/save-220120.log` | Memory log | N/A | LOW | N/A |
| `./.remember/logs/autonomous/save-220127.log` | Memory log | N/A | LOW | N/A |
| `./.remember/logs/autonomous/save-220209.log` | Memory log | N/A | LOW | N/A |
| `./.remember/logs/hook-errors.log` | Memory log | N/A | LOW | N/A |
| `./.remember/logs/memory-2026-06-11.log` | Memory log | N/A | LOW | N/A |
| `./.remember/logs/memory-2026-06-12.log` | Memory log | N/A | LOW | N/A |
| `./.remember/logs/memory-2026-06-13.log` | Memory log | N/A | LOW | N/A |
| `./.remember/logs/memory-2026-06-14.log` | Memory log | N/A | LOW | N/A |
| `./.remember/logs/memory-2026-06-15.log` | Memory log | N/A | LOW | N/A |
| `./.remember/logs/memory-2026-06-16.log` | Memory log | N/A | LOW | N/A |
| `./.remember/logs/memory-2026-06-17.log` | Memory log | N/A | LOW | N/A |
| `./.remember/logs/memory-2026-06-18.log` | Memory log | N/A | LOW | N/A |
| `./.remember/now.md` | Memory log | N/A | LOW | N/A |
| `./.remember/recent.md` | Memory log | N/A | LOW | N/A |
| `./.remember/remember.md` | Memory log | N/A | LOW | N/A |
| `./.remember/tmp/last-ndc.ts` | Memory log | N/A | LOW | N/A |
| `./.remember/tmp/last-save-ts` | Memory log | N/A | LOW | N/A |
| `./.remember/tmp/last-save.json` | Memory log | N/A | LOW | N/A |
| `./.remember/tmp/save-session.pid` | Memory log | N/A | LOW | N/A |
| `./.remember/today-2026-06-11.done.md` | Memory log | N/A | LOW | N/A |
| `./.remember/today-2026-06-12.done.md` | Memory log | N/A | LOW | N/A |
| `./.remember/today-2026-06-13.done.md` | Memory log | N/A | LOW | N/A |
| `./.remember/today-2026-06-14.done.md` | Memory log | N/A | LOW | N/A |
| `./.remember/today-2026-06-15.done.md` | Memory log | N/A | LOW | N/A |
| `./.remember/today-2026-06-16.done.md` | Memory log | N/A | LOW | N/A |
| `./.remember/today-2026-06-17.done.md` | Memory log | N/A | LOW | N/A |
| `./.remember/today-2026-06-18.md` | Memory log | N/A | LOW | N/A |
## Pytest Cache (Root)

| File | Purpose | Tests | Risk | Status |
|------|---------|-------|------|--------|
| `./.pytest_cache/.gitignore` | Git/cache metadata | N/A | LOW | N/A |
| `./.pytest_cache/CACHEDIR.TAG` | .tag file | N/A | LOW | N/A |
| `./.pytest_cache/README.md` | Documentation | N/A | LOW | N/A |
| `./.pytest_cache/v/cache/lastfailed` |  file | N/A | LOW | N/A |
| `./.pytest_cache/v/cache/nodeids` |  file | N/A | LOW | N/A |
## Codex Config

| File | Purpose | Tests | Risk | Status |
|------|---------|-------|------|--------|
| `./.codex/config.toml` | TOML config | N/A | LOW | N/A |
| `./.codex/hooks.json` | JSON/config | N/A | LOW | N/A |
## Worktrees (Other Branches)

| File | Purpose | Tests | Risk | Status |
|------|---------|-------|------|--------|
| `./.worktrees/phase-0-7/ios/StockApp/stockme/stockme/Charts/StockCharts.swift` | Swift source | N/A | HIGH | N/A |
| `./.worktrees/phase-0-7/ios/StockApp/stockme/stockme/Models.swift` | Swift source | N/A | LOW | N/A |
| `./.worktrees/phase-0-7/ios/StockApp/stockme/stockme/Utilities/Theme.swift` | Swift source | N/A | HIGH | N/A |
| `./.worktrees/phase-0-7/ios/StockApp/stockme/stockme/Views/ExpertNetworkView.swift` | Swift source | N/A | LOW | N/A |
| `./.worktrees/phase-0-7/ios/StockApp/stockme/stockme/Views/NewsMultimediaView.swift` | Swift source | N/A | LOW | N/A |
| `./.worktrees/phase-0-7/ios/StockApp/stockme/stockme/Views/SettingsScreen.swift` | Swift source | N/A | LOW | N/A |
## root

| File | Purpose | Tests | Risk | Status |
|------|---------|-------|------|--------|
| `./.gitignore` | Git/cache metadata | N/A | LOW | N/A |
| `./00_STATE.md` | Documentation | N/A | LOW | N/A |
| `./AGENTS.md` | Documentation | N/A | LOW | N/A |
| `./CLAUDE.md` | Documentation | N/A | LOW | N/A |
| `./GEMINI.md` | Documentation | N/A | LOW | N/A |
| `./Nivesh_Backend_AI_Proposal.docx` | Word doc | N/A | LOW | N/A |
| `./README.md` | Documentation | N/A | LOW | N/A |
| `./RESPONSIVE_LAYOUT_IMPLEMENTATION.md` | Documentation | N/A | LOW | N/A |
| `./backend_test_audit_report.md` | Test | N/A | LOW | N/A |
| `./commit.sh` | Shell script | N/A | LOW | N/A |
| `./fix_ui.py` | Python module | NO | LOW | untested |
| `./gen_prompts.py` | Python module | NO | LOW | untested |
| `./health_check.sh` | Shell script | N/A | LOW | N/A |
| `./install-agents.sh` | Shell script | N/A | LOW | N/A |
| `./patch_app.py` | Python module | NO | LOW | untested |
| `./scratch_corr_test.py` | Python module | NO | LOW | untested |
| `./test_all.sh` | Test | N/A | LOW | N/A |
| `./test_api.py` | Test | YES | LOW | tested |
| `./test_fastapi_serialize.py` | Test | NO | LOW | untested |
| `./test_morning.py` | Test | NO | LOW | untested |
| `./test_write.txt` | Test | N/A | LOW | N/A |
| `./update_maps.py` | Python module | NO | LOW | untested |