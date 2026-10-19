# Feature package platform-scheduler-ist: One IST scheduler: explicit ids, job_runs tracking, market-hours alerts, canary and drill registration

Cluster: platform (Platform, operations and privacy); area: backend
Features covered: 32 I09 Dedicated worker, one IST scheduler, 30 I08 Observability baseline, 56 I48 Leave the home server

## Files (create or modify)
- backend/services/harvest_worker.py
- backend/services/model_canary.py
- backend/services/research/jobs.py
- backend/tests/test_scheduler_ist.py
- backend/tests/test_model_canary.py
- backend/tests/morning_briefing/test_scheduler.py
- backend/tests/morning_briefing/test_regression.py
- docs/codebase/SCHEDULER.md
- backend/.env.example

## Dependencies
- Feature packages (integrated before you start): platform-jobruns, platform-restore-drill
- Declared in the plan: platform-jobruns, platform-restore-drill, FIX:REL-03, FIX:REL-12, FIX:SILENT-13, FIX:SILENT-18, FIX:REL-09, FIX:ML-03, FIX:OPS-03, FIX:PERF-15, FIX:PERF-19, FIX:REL-21, FIX:LLM-26, FIX:AUTH-01, FIX:DB-13, FIX:ARCH-07, FIX:ARCH-03, FIX:LLM-02, FIX:DB-24, ENG:be-ingest-jobs, ENG:be-wiring. FIX:/ENG: items may or may not be on the tip yet: check the code; where one is missing, build against the documented interface behind the flag and report it.

## Description
I09 smaller version: one scheduler in IST and no separate process. It also registers I08's canary and I48's drill. Land it right after the fix track and ENG:be-wiring, and before any other cluster adds scheduler jobs.

services/harvest_worker.py start_scheduler, starting from its state after the fix track and be-wiring:

1. Module-level helper _track_all_jobs(scheduler):
- Replace scheduler.add_job with a function that wraps func in job_runs.tracked(kwargs.get('id') or func.__name__, func) and then delegates to the original bound method.
- tracked() returns an async wrapper for coroutine functions. AsyncIOScheduler therefore still runs async jobs on its event loop and sync jobs in its thread pool.
- Call it immediately after constructing _scheduler. Every job then records job_runs rows, including register_research_jobs and future jobs from other clusters.

2. Construct AsyncIOScheduler(timezone='Asia/Kolkata', job_defaults=<FIX:REL-03 values unchanged>).
- Keep the literal AsyncIOScheduler(...) call so the morning-briefing AST tests can still read it.

3. After the fcntl lock is acquired (leader only), call job_runs.mark_abandoned() inside try/except.

4. Give every add_job an explicit id=. Convert each cron job's hour, minute and day_of_week from UTC to IST wall clock by adding 05:30. If the IST time crosses midnight, shift day_of_week names forward one day. Interval jobs keep their trigger.
- Expected post-fix-track table (UTC to IST, then id):
  - advisor harvest 01:30 to 07:00, 'advisor_harvest'. Keep a '# 07:00 IST' comment on this line for FIX:LLM-26's test.
  - snapshot_all_users 11:00 to 16:30, 'portfolio_snapshot'.
  - run_nightly_screen 11:15 to 16:45, 'nightly_screen'.
  - _run_evaluate_analysis_outcomes 20:30 to 02:00, 'legacy_outcome_eval' (if still present).
  - notification cleanup 21:30 to 03:00, 'notification_cleanup'.
  - preferences backfill 21:35 to 03:05, 'preferences_backfill'.
  - bhavcopy 13:30 to 19:00, 'bhavcopy'.
  - morning brief pregen 01:00 to 06:30, 'morning_brief_pregen'.
  - piotroski sun 17:30 to sun 23:00, 'piotroski_weekly'.
  - error digest 01:30 to 07:00, 'error_digest'.
  - db backup (FIX:OPS-03) 21:00 to 02:30, 'db_backup'.
  - prediction outcomes (FIX:ML-03) 21:00 to 02:30, 'prediction_outcomes'.
  - rag ingest (FIX:REL-21) 21:45 to 03:15, 'rag_ingest'.
  - retention (FIX:PERF-15) 21:45 to 03:15, 'retention'.
  - deletion processing 22:00 to 03:30, 'deletion_requests' (only if FIX:DB-06 added it).
  - anomaly scan: convert whatever FIX:PERF-19 left; hourly minute=0 stays hourly. Id 'anomaly_scan'.
  - Interval jobs keep or get ids 'news_harvest', 'youtube_metadata', 'youtube_portfolio', 'expert_harvest', 'sebi_harvest', 'youtube_expert_harvest'.
- Drop rows whose job no longer exists. Convert any unlisted job with the same rule. Comments become '# HH:MM IST'.

5. Price alerts ('price_alerts', FIX:REL-09): replace the 5-minute interval with 'cron', day_of_week='mon-fri', hour='9-15', minute='*/5'. That fires every 5 minutes from 09:00 to 15:55 IST on weekdays. REL-09's atomic claim keeps each alert exactly once.

6. New jobs, using local imports like the other jobs:
- add_job(run_model_canary, 'cron', hour=8, minute=30, id='model_canary').
- add_job(run_restore_drill, 'cron', day=1, hour=4, minute=0, id='restore_drill').

7. Make job failures visible to job_runs:
- Every job wrapper whose except block swallows the exception gets a bare raise as its last statement. The pattern is: except Exception, then _dash_update_harvest(<key>, 'error', ...) or logger.exception, then fall through.
- The job's work is otherwise unchanged.
- Update the 'All schedulers started' log string to IST times.

services/research/jobs.py (ENG:be-ingest-jobs):
- Add timezone='UTC' to each of the 7 cron add_job calls in register_research_jobs. Leave the cron fields unchanged: the windows start at :30 IST, so they stay defined in UTC. The engine's cron-field test still passes.

services/model_canary.py (new), run_model_canary() -> dict:
- If os.getenv('CANARY_ENABLED', '1').strip().lower() is one of '0', 'false', 'off' or 'no', return {'skipped': 'disabled'} without any LLM call. It is an ops job, so it uses env rather than a server flag.
- Models: {llm_utils.DEEPSEEK_MODEL, llm_utils.HAIKU_MODEL, llm_utils.SONNET_MODEL} plus the comma list CANARY_EXTRA_MODELS.
- Per model:
  - Return 'skipped_no_key' when the provider key is unset. Models whose names start with 'deepseek' need DEEPSEEK_API_KEY; models starting with 'claude' need ANTHROPIC_API_KEY.
  - deepseek models: llm_utils.deepseek_chat([{'role': 'user', 'content': 'ping'}], max_tokens=1, temperature=0, model=m, log_endpoint='model_canary').
  - claude models: llm_utils.claude_messages(model=m, messages=<the same>, max_tokens=1, feature='model_canary') (FIX:ARCH-03; adapt kwarg names to the gateway's final signature).
  - LlmBudgetExceeded (FIX:LLM-02; guard the import, with a local fallback class) gives 'skipped_budget'.
  - Any other exception gives 'error: <ExceptionType>'.
- If any model errored, raise CanaryFailure('models failing: a, b'); tracked records it and alerts. Otherwise return {'models': results}.
- Never log prompts or keys.

docs/codebase/SCHEDULER.md (new): the IST table above, plus the research UTC jobs with their IST equivalents. Rules for new jobs:
- use IST wall clock;
- use timezone='UTC' only for windows that are defined in UTC;
- always pass id=;
- write jobs as plain def (FIX:REL-03) that raise on failure;
- tracking happens automatically for sync and async jobs.

.env.example: add CANARY_ENABLED (default on) and CANARY_EXTRA_MODELS.

Update the existing tests:
- tests/morning_briefing/test_scheduler.py: rename test_timezone_utc to test_timezone_ist and expect 'Asia/Kolkata'. Expect the pregen job at hour=6, minute=30 if it still exists; otherwise skip that test.
- tests/morning_briefing/test_regression.py B2: accept timezone='Asia/Kolkata' in either quote style.

## Acceptance checks
- AST parse and pyright are clean on the touched files.
- tests/test_scheduler_ist.py passes in CI. Harness:
  - a FakeScheduler that records constructor kwargs and add_job(func, trigger, **kw);
  - services.harvest_worker.AsyncIOScheduler monkeypatched to it;
  - a no-op fcntl.lockf;
  - a counter on job_runs.mark_abandoned.
  It checks:
  - the constructor timezone is 'Asia/Kolkata';
  - every add_job has a unique id;
  - every registered func has _job_runs_name;
  - a registered async def job is still a coroutine function after wrapping;
  - every expected IST wall-clock time, computed with CronTrigger(timezone=IST, **fields).get_next_fire_time(None, Monday 2026-10-12 00:00 IST);
  - price_alerts fires next at Mon 2026-10-19 09:00 when checked from Sat 2026-10-17 10:00, and at Tuesday 09:00 when checked from Monday 15:56;
  - model_canary is at 08:30 and restore_drill on day 1 at 04:00;
  - mark_abandoned is called once;
  - with the research config's effective mode monkeypatched to shadow, register_research_jobs(fake) adds cron jobs that all have timezone 'UTC'.
- tests/test_model_canary.py passes:
  - CANARY_ENABLED=0: skipped, with no LLM calls;
  - both providers are pinged with max_tokens=1;
  - a missing key gives skipped_no_key;
  - a budget exception gives skipped_budget without raising;
  - a failing model raises CanaryFailure naming it.
- The updated morning_briefing tests and the existing fix-track scheduler tests still pass.

## Cluster spec
docs/feature-specs/spec_platform.md holds the reviewed spec for the whole cluster (data model, API contracts, iOS states, flags, copy, tests) and the coverage table. Read the parts for your features and files; the contract written there is binding for both the backend and the iOS package of a feature.

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
