# Feature package data-wiring: Register IST data jobs, mount routers before portfolio/stocks, delete legacy bhavcopy job, document feeds

Cluster: data (Data foundation); area: backend
Features covered: I14, I15, I16, I17, I18, I25, C15

## Files (create or modify)
- backend/services/data_jobs.py
- backend/services/harvest_worker.py
- backend/services/nse_data_provider.py
- backend/main.py
- backend/tests/test_data_wiring.py
- docs/data/DATA_FEEDS.md

## Dependencies
- Feature packages (integrated before you start): data-amfi-backend, data-corpactions-backend, data-eod-mirror, data-instruments, data-results-backend
- Declared in the plan: data-eod-mirror, data-amfi-backend, data-instruments, data-corpactions-backend, data-results-backend, ENG:be-wiring, FIX:REL-12, FIX:REL-03, FIX:DB-13, FIX:PERF-19, FIX:MATH-07, FIX:ARCH-19. FIX:/ENG: items may or may not be on the tip yet: check the code; where one is missing, build against the documented interface behind the flag and report it.

## Description
New services/data_jobs.py.

JOBS = (job_id, 'module:function', cron):
- data_eod_mirror_evening: services.eod_prices:mirror_recent, mon-fri 21:40
- data_eod_mirror_morning: services.eod_prices:mirror_recent, tue-sat 07:40
- data_amfi_nav_night: services.amfi:harvest, 23:30
- data_amfi_nav_morning: services.amfi:harvest, 08:10
- data_equity_master: services.instruments:refresh_equity_master, sat 08:30
- data_results_feed: services.results_digest:poll_feed_job, hour '8-23', minute '5,35'
- data_results_numbers: services.results_digest:fill_pending_numbers, 22:15

run_job(job_id, target):
- importlib lazy import; call with no args; log the dict at INFO.
- On an exception: logging.exception plus error_telemetry.log_diagnostic_error(subsystem='DATA_FEEDS', classification=job_id, context={'error': type name}). Never re-raise.

register_data_jobs(scheduler) -> list[str]: add_job(run_job, 'cron', args=[id, target], id=id, timezone='Asia/Kolkata', max_instances=1, coalesce=True, misfire_grace_time=3600, replace_existing=True, **cron).

harvest_worker.start_scheduler:
- Before _scheduler.start(), add a guarded call: try: register_data_jobs(_scheduler); except Exception: logging.critical(..., exc_info=True). Keep be-wiring's research hook too.
- Delete _run_bhavcopy_download, its add_job and the download_bhavcopy import.
- Leave MATH-07's job. If I09 moved the scheduler, put the call in the new location.

nse_data_provider.py: delete download_bhavcopy (no callers after PERF-19).

main.py: import routers.corporate_actions and routers.results_digest, and add their include_router lines BEFORE app.include_router(portfolio.router) (main.py:271 today), and therefore before stocks.router (main.py:299). No present or future path parameter on those routers can then capture them.

New docs/data/DATA_FEEDS.md:
- sources, licences and legal items with outcomes
- the honest-UA policy
- the IST job table, including MATH-07's job and the created_at guard
- the flag table with defaults, FEATURE_<KEY>_USERS cohorts and who may flip each flag
- tables, growth and retention
- the §0.5 contracts: EQ and INDEX closes are not shown to users until data_eod_display is on; callers handle None with their own labelled source
- a review query for MATH-07 auto SPLIT rows written before the guard: SPLIT rows whose notes start 'auto: corporate action', where the same user, group and ticker has a row dated before the SPLIT but created on or after the ex-date (the SPLIT date plus one day)
- the deferral conditions for data_corp_actions_confirm and data_results_digest, and the data_eod_display condition
- the I17 follow-on design: shareholding_patterns gains period_end, source, source_url, filed_on, updated_at and a unique (ticker, period_end); Indian-FY labels (2026-09-30 is Q2 FY27); optional FII/DII/public/pledge, never invented; ordered by period_end; flag data_shareholding, default off; prerequisite is a licensed vendor or written exchange permission plus legal sign-off; no hand-copied exchange tables
- the C15 end state: Stage 3 unschedules ingest_new; Stage 4 deletes rag_ingestion, rag_tools and vector_store (and their backup_service reference) and drops nivesh_filings
- DPDP: the table is in ERASURE_POLICY and must be in the I06 export

## Acceptance checks
PYPARSE and PYRIGHT clean.

test_data_wiring.py covers:
- a fake scheduler records 7 ids, each with Asia/Kolkata, max_instances 1 and coalesce True
- run_job swallows an exception and calls the patched log_diagnostic_error once
- an AST guard: register_data_jobs is called inside Try/except Exception before _scheduler.start(), and download_bhavcopy is gone
- route order: for GET /api/v1/portfolio/corporate-actions and GET /api/v1/stocks/TCS/results-digest, the first app.router.routes entry whose matches(scope) is Match.FULL has its endpoint in routers.corporate_actions and routers.results_digest respectively
- in main.py source, both include lines come before portfolio.router and stocks.router

grep finds no download_bhavcopy outside tests; ARCH-19's find_unreferenced_modules.py passes.

## Cluster spec
docs/feature-specs/spec_data.md holds the reviewed spec for the whole cluster (data model, API contracts, iOS states, flags, copy, tests) and the coverage table. Read the parts for your features and files; the contract written there is binding for both the backend and the iOS package of a feature.

## Constraints (hard rules)
- Fix track and engine: the audit-fix track and the Research Engine are integrated (or integrating) on the same line. Build on their code; never re-implement what they already do. If a dependency is not in the code yet, do not stub or duplicate it: build your part against the documented interface behind the feature flag, and report it.
- Research Engine decisions win: every number is computed by validated code; DeepSeek only phrases computed facts behind the grounding validator; no buy/sell/hold, price targets or stock-level probabilities; English-only v1; legacy analysis routes are retired (410); track record and cohort display only when RESEARCH_SEBI_RA_REG_NO is set. Where a feature conflicts, the engine decision is the default and the feature sits behind a flag that is off.
- Compliance: no advice, recommendations, ratings or targets; no performance claims in marketing or share content; never claim SEBI registration; DPDP Act 2023 / Rules 2025 (consent, purpose limitation, erasure, export, breach logging); App Store rules (5.1.1 account deletion, StoreKit for digital goods, privacy manifest).
- Engineering: ORM models only in backend/models/db_models.py; schema changes only via a new Alembic revision with a RANDOM 12-hex id chained to the current single head; DB access through get_session(); thin routers, logic in services/; Lakhs/Crores; iOS colours only Theme.* tokens, stripEmoji on AI text, no GeometryReader inside ScrollView/HStack, no nested NavigationStack, ViewBuilder helpers over 5 lines become View structs; free, terms-respecting data sources only (AMFI NAV files, NSE/BSE public files, yfinance) with an honest User-Agent (contact https://github.com/snp05016/nivesh); no new third-party dependency unless the brief names one; every new surface behind a server-side feature flag (reuse the project's flag mechanism) that degrades gracefully; every feature with tests.
- Backend code cannot be executed here: static checks plus hermetic tests that are correct by construction. iOS: swiftc -parse only. ml-engine code can be executed and its tests must pass.

## Local test commands
- ml-engine: cd <your worktree>/ml-engine && PYTHONDONTWRITEBYTECODE=1 backend/venv/bin/python -m pytest -p no:cacheprovider -q <tests>
- backend: static checks only (pycheck, pyright_delta); tests hermetic and correct by construction.
- iOS: swiftc -parse only; verify every symbol you use by grepping its declaration.
