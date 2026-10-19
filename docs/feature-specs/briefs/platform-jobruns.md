# Feature package platform-jobruns: job_runs history, sync/async tracked() wrapper, failure alerts and retention

Cluster: platform (Platform, operations and privacy); area: backend
Features covered: 30 I08 Observability baseline

## Files (create or modify)
- backend/models/db_models.py
- backend/migrations/versions/24a2a72cebb6_add_job_runs.py
- backend/services/job_runs.py
- backend/routers/dashboard.py
- backend/services/retention.py
- backend/services/error_telemetry.py
- backend/tests/test_job_runs.py
- docs/codebase/OBSERVABILITY.md
- backend/core/dashboard_state.py
- backend/tests/test_scheduler_jobs.py

## Dependencies
- Feature packages (integrated before you start): platform-flags
- Declared in the plan: platform-flags, FIX:SILENT-13, FIX:REL-12, FIX:SILENT-17, FIX:OPS-14, FIX:PERF-15, FIX:REL-16, FIX:ARCH-05, FIX:DB-24. FIX:/ENG: items may or may not be on the tip yet: check the code; where one is missing, build against the documented interface behind the flag and report it.

## Description
I08 smaller version, part 1: a durable per-run job history. It is the only persisted job status, because human step 1 trims FIX:SILENT-13's scheduler_job_status before wave p2-50 runs.

0. Check first. If backend/models/db_models.py contains class SchedulerJobStatus, SILENT-13 landed untrimmed: also do every item marked UNTRIMMED. Otherwise skip those items, and leave core/dashboard_state.py and tests/test_scheduler_jobs.py untouched.

1. models/db_models.py: append class JobRun(Base) with __tablename__ 'job_runs' and these columns:
   - id: Integer PK, autoincrement.
   - job_name: String(64), NOT NULL.
   - status: String(16), NOT NULL, with CheckConstraint status IN ('running','ok','failed') named ck_job_runs_status.
   - started_at: DateTime, NOT NULL, default _utcnow.
   - finished_at, duration_ms, rows_written: NULL (DateTime, Integer, Integer).
   - error: Text NULL.
   - meta: JSON(none_as_null=True) NULL.
   - Indexes: ix_job_runs_job_started (job_name, started_at) and ix_job_runs_status_started (status, started_at).
   UNTRIMMED: delete class SchedulerJobStatus.

2. migrations/versions/24a2a72cebb6_add_job_runs.py:
   - Revision '24a2a72cebb6'. down_revision = the head after platform-flags (ba5740a03b6b unless another migration landed between).
   - Upgrade: create job_runs and both indexes if missing. Downgrade: drop job_runs if present.
   - UNTRIMMED: the upgrade also drops scheduler_job_status if present. The downgrade recreates it if missing, with: job_name String(64) PK; status String(16); last_started_at and last_finished_at DateTime NULL; last_error Text NULL; last_result_json Text NULL; updated_at DateTime.

3. services/job_runs.py (stdlib + httpx). Bookkeeping never raises; failures only log warnings.
   - tracked(job_name, fn):
     - If inspect.iscoroutinefunction(fn), return an async def wrapper decorated with functools.wraps(fn):
       - run_id = await asyncio.to_thread(start_run, job_name);
       - result = await fn(*args, **kwargs);
       - then await asyncio.to_thread(finish_run, run_id, 'ok', result=result, duration_ms=...);
       - return result.
       - On an exception: await asyncio.to_thread(finish_run, run_id, 'failed', error=f'{type(exc).__name__}: {exc}', duration_ms=...), then re-raise.
       The job stays on the scheduler's event loop. Bookkeeping, including the alert POST, runs in a thread, so it never blocks the loop.
     - Otherwise, return a sync wrapper (functools.wraps) with the same steps, calling start_run and finish_run directly.
     - Both wrappers carry the attribute _job_runs_name = job_name, and duration comes from time.monotonic.
     - There is no asyncio.run anywhere: an async job must never move to a new loop in a worker thread.
   - start_run(job_name) -> int|None: inserts a row with status 'running'.
   - finish_run(run_id, status, *, error=None, result=None, duration_ms=None): sets finished_at and duration_ms, plus:
     - rows_written: an int result, or the first non-bool int among the dict keys rows_written, rows, added, count, generated and chunks.
     - meta: a dict result made JSON-safe with json.dumps(default=str); if the serialised length exceeds 4000, store {'truncated': true}. An int or str result is stored as {'result': value}.
     - error = scrub(error).
     Alert rule:
     - On 'failed', when the previous finished run of the same job_name was not 'failed' (or there is none): notify_ops('Nivesh job failed: <job>', scrub(error)[:300]).
     - On 'ok', when the previous finished run was 'failed': notify_ops('Nivesh job recovered: <job>', '').
   - scrub(text): replace emails with <email>, the PAN pattern [A-Z]{5}[0-9]{4}[A-Z] with <pan>, 'Bearer <token>' with 'Bearer <redacted>', '://user:pass@' with '://<redacted>@', and runs of 10 or more digits with <number>. Truncate to 2000 chars.
   - notify_ops(title, body) -> bool: POST to OPS_ALERT_WEBHOOK_URL (env introduced by FIX:OPS-14; ntfy-compatible plain-text body with a 'Title' header), timeout 5 s. If the URL is unset, log a warning and return False.
   - mark_abandoned() -> int: every 'running' row becomes 'failed' with error 'abandoned: scheduler restarted' and finished_at = now. No alert.
   - latest_by_job() -> dict[job_name, row dict], using a subquery of max(id) per job_name.
   - list_runs(job_name=None, status=None, limit=50, before_id=None) -> list[dict]: limit clamped to 1..200, ordered by id desc.
   - summary(days=7) -> {'days', 'overall_success_pct', 'jobs'}:
     - overall_success_pct is None when there are no finished runs.
     - Each job entry has job_name, runs, failures, success_pct, last_status, last_started_at and last_error.
     - Compute it in Python over finished runs since now - days, with days clamped to 1..90.
     - Add the comment '# ponytail: python aggregation, move to SQL GROUP BY past ~100k rows'.
   - purge_older_than(days=90) -> int.
   - Row dicts serialise datetimes as ISO-8601 with a trailing Z; they are stored as naive UTC per FIX:DB-24.

4. routers/dashboard.py: where harvest_status is built, start from dict(core.dashboard_state._harvest_status). For job names missing from it, add entries from job_runs.latest_by_job(), mapped to:
   - 'status': running stays running, ok becomes idle, failed becomes error;
   - 'last_run': started_at;
   - 'last_result': {'error': error} when error is set, else meta.
   UNTRIMMED: this replaces SILENT-13's read from scheduler_job_status.

5. UNTRIMMED only:
   - core/dashboard_state.py: delete _persist_job_status and its call inside _dash_update_harvest, and keep the in-memory setdefault.
   - tests/test_scheduler_jobs.py: SILENT-13's test (b) asserts only the in-memory _harvest_status entry.

6. services/retention.py (FIX:PERF-15 run_retention): add step 'job_runs' = job_runs.purge_older_than(90) in its own try/except, and include its count in the returned dict.

7. services/error_telemetry.py generate_daily_digest: add a 'Scheduled jobs (last 24h)' block from job_runs.summary(days=1), with runs, failures and up to 10 failing job names with counts. If the query fails, write 'Scheduled jobs: UNKNOWN - query failed' (FIX:SILENT-17's honesty rule).

8. docs/codebase/OBSERVABILITY.md: document:
   - what job_runs records, and that sync and async jobs are both tracked;
   - the alert rule and the 300-character body cap;
   - the canary (registered by platform-scheduler-ist; switched off with CANARY_ENABLED=0);
   - 90-day retention and the expected volume (about 2,000 rows a week, about 25,000 at 90 days);
   - where to look (admin Jobs page; journalctl -u nivesh) and SQL snippets;
   - the alert relay: use a self-hosted ntfy server or an access-controlled topic, because anyone who knows a public ntfy.sh topic name can read it. The relay is listed as a processor in docs/compliance/DPDP_RUNBOOK.md and the export.
   Deferred items:
   - the data-status endpoint and footers;
   - merging the *_error_logs tables;
   - GlitchTip and crash upload;
   - missed-run detection;
   - the thread-pool remedy: if /health latency rises while CPU is idle, set anyio.to_thread.current_default_thread_limiter().total_tokens at startup. Not built until measured.

## Acceptance checks
- AST parse and pyright pass on all touched files.
- A static parse of migrations/versions shows a single head.
- In CI, the Alembic upgrade/downgrade/upgrade cycle on SQLite passes. UNTRIMMED case: scheduler_job_status is dropped on upgrade and restored on downgrade.
- tests/test_job_runs.py passes in CI, covering:
  - a success row with duration and rows_written;
  - a failure row with a scrubbed error and the exception re-raised;
  - for an async def job: inspect.iscoroutinefunction(tracked('x', job)) is True, a successful run (driven by asyncio.run inside the test) writes an ok row, and a raising one writes a failed row and re-raises;
  - a monkeypatched get_session that raises: the job still runs and returns its result;
  - notify_ops called only on the first failure of a streak and on recovery, with a body of at most 300 characters;
  - mark_abandoned flipping running rows;
  - summary percentages;
  - list_runs pagination;
  - each scrub case;
  - purge_older_than;
  - run_retention reporting a job_runs count;
  - the digest containing 'Scheduled jobs'.
- grep finds no 'asyncio.run' in services/job_runs.py.
- UNTRIMMED case: the updated tests/test_scheduler_jobs.py passes, and grep finds no SchedulerJobStatus or _persist_job_status.

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
