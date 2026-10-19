# Cluster 'platform': Platform, operations and privacy

Roadmap: docs/investigations/2026-10-08_deep-audit/EXPANSION_ROADMAP.md

## Coverage and council handling

| Feature | Status | Verdict handling | Evidence |
|---|---|---|---|
| 30 I08 Observability baseline | partial | Simplify: built the smaller version, 'job_runs plus the canary' (platform-jobruns, platform-scheduler-ist), with three cheap additions: alerts on the first failure and on recovery through the existing OPS-14 webhook (body capped at 300 scrubbed characters; the relay is listed as a processor), a jobs section in the daily digest, and an admin Jobs page. tracked() keeps async jobs on the scheduler's event loop and has no asyncio.run path. SILENT-13 is trimmed before its wave runs (human step 1), so job_runs is the only persisted job status and no table is created and then dropped. platform-jobruns keeps a fallback in case p2-50 already ran untrimmed. The canary is switched by env CANARY_ENABLED, not by a flag. Deferred, with conditions in OBSERVABILITY.md: /api/v1/data-status and user-facing 'as of' footers (engine reports already show staleness), merging the four *_error_logs tables, GlitchTip or consented crash upload, missed-run detection, and a thread-pool size knob. | Already delivered by the fix track: FIX:SILENT-13, FIX:REL-12, FIX:PERF-25 and FIX:OPS-18 fix the logger NameErrors, delete the two cache jobs that crash every run (harvest_worker.py:180 and :230) and stop dropping unknown dashboard keys. FIX:SILENT-17 stops the digest printing 'clean run' when its query failed. FIX:OPS-14 posts the daily digest to OPS_ALERT_WEBHOOK_URL and adds logrotate and uptime-monitor docs. FIX:REL-18 makes /health and /health/ready DB-backed and /healthz admin-only. FIX:ARCH-05, FIX:REL-16 and FIX:LLM-09 leave one dashboard state and a correct cost panel. FIX:DB-24 removes the UTC+4 staleness offset and adds core/timeutil IST helpers. FIX:ML-24 covers ml-engine readiness. The engine adds the /healthz research block and the research_runs heartbeat (SPEC §2.7; ENG:be-ingest-jobs, ENG:be-wiring). SILENT-13 (wave p2-50, not yet run: the worktree has no SchedulerJobStatus) also plans a one-row-per-job scheduler_job_status table, and its planned migration id t4u5v6w7x8y9 is already used by the engine's research-tables migration. Still missing: per-run history, an alert for each job failure, and any check that the hard-coded model ids in llm_utils.py:28-30 still resolve. |
| 32 I09 Dedicated worker, one IST scheduler | partial | Simplify: built the smaller version without a separate process. The scheduler runs in Asia/Kolkata with IST cron fields and explicit job ids. Research cron windows stay pinned to timezone='UTC', because they start at :30 IST. Price alerts run only 09:00-15:55 IST on weekdays. Tests check that each job is registered once and fires at the expected IST time. Tutorial step 8 is rewritten as a price alert ('alert prices', not 'target price', which is research-call vocabulary under the SEBI RA amendments). The dedicated worker process (claimed_by and attempts) is deferred. The engine already moved heavy compute into the ml-engine container, and legacy analysis jobs retire at engine Stage 3. CLOUD_MIGRATION.md records the trigger: more than one API process or host. | FIX:REL-03 turns every job into a plain def and sets job_defaults, but it keeps AsyncIOScheduler(timezone='UTC') (harvest_worker.py:117) and the UTC cron fields on purpose. FIX:REL-12, FIX:SILENT-13 and FIX:OPS-18 remove the crashing jobs, Celery, _run_harvest_filings and check_signal_outcomes. FIX:REL-09 moves the price poller into the scheduler leader with an atomic claim, but it still runs every 5 minutes around the clock. FIX:REL-21, FIX:DB-13, FIX:ARCH-07 and FIX:REL-08 schedule RAG ingestion, keep one-time startup tasks on the leader only, and run a single worker. Outcome scoring comes from FIX:ML-03 and the engine's research_score_outcomes (ENG:be-ingest-jobs). Owned by other clusters: the AMFI NAV harvest (data cluster, I16) and filings (I31/C15). Tutorial step 8 still promises alerts 'every time you open the app' and uses 'target price' wording (Views/TutorialOverlayView.swift:91). |
| 46 C12 Stop blocking the event loop | partial | Build: the handler fixes are fix-track work. This cluster adds the missing rule in two parts (platform-async-guard). First, ruff's own flake8-async codes for blocking I/O (ASYNC210, 220, 221, 222, 230 and 251) are added to TEST-14's gate, so they cover the whole backend including services/, with a shrink-only per-file-ignores baseline in a new backend/ruff.toml. Second, a small stdlib-AST test covers what ruff cannot know: project blocking calls (get_session, deepseek_chat, claude_messages, claude_haiku, yfinance) inside async def in routers, core, middleware, services and main.py, and awaits whose callee resolves exactly to a sync def (same module, a backend import alias, or a method of the same class). Attribute calls on third-party objects are never flagged, and an '# async-ok: reason' comment covers justified cases. The thread-pool knob is not built; OBSERVABILITY.md documents it as the remedy if /health latency shows starvation. An async LLM gateway is deliberately not built: REL-01 makes every LLM caller sync, and the test keeps sync LLM calls out of async def. | Already delivered by the fix track: FIX:REL-01 converts the 25 await-free async handlers (copilot, analyze, polling, market, portfolio) to def and adds tests for await-free routes and /ping responsiveness. FIX:PERF-02 converts the remaining handlers and FIX:REL-03 the scheduler. FIX:REL-07 fixes the brief's await-on-sync (portfolio_snapshot.py:232). FIX:LLM-13, FIX:REL-22 and ENG:be-cutover remove copilot's process fork and its 60 s q.get (copilot_service.py:136-142). FIX:REL-11 fixes the SSE stream, and FIX:DB-23 is covered by those items. Gap: PERF-02 says REL-01 owns a ruff ASYNC gate, but REL-01's plan has none. FIX:TEST-14 pins ruff 0.8.6 and gates only --select E9,F63,F7,F82 on the command line; the repository has no ruff config file. Nothing catches a blocking call in an async def that also awaits, or an 'await' on a sync function. |
| 36 I47 First-party product analytics | new | Simplify: the ten events only. Two are renamed for the engine: report_view and report_compute replace analysis_start and analysis_view, because the engine serves stored reports and retires /analyze. Each event has a strict prop allowlist of enumerated values, so tickers, holdings, amounts and free text can never be stored. Consent is opt-in ('product_analytics') and checked on the server for every batch. It is asked for once in context, through a neutral Home card with equal-weight 'Allow' and 'Not now' buttons (the review's option (a)), so the sample is large enough to measure. Withdrawal erases the user's events right after it commits, and the daily retention step deletes the events of anyone without an active consent (DPDP s.6(4)-(6) and s.8(7)). Retention is USER_EVENTS_RETENTION_DAYS (default 180), and the server sends it to iOS. The Rule 8(3) one-year question is an owner and legal decision recorded in the runbook. Delivered as SQL docs plus a small admin Usage page that shows 'active users'. UX's extra events are deferred; adding one is an allowlist change with no migration. The surface sits behind flag 'analytics', OFF by default, until the privacy policy names analytics. The App Store privacy label is updated in the first binary that contains EventLogger. App Store Connect analytics remains the free baseline. | There is no analytics SDK, events table or events route. backend/telemetry_spec.json describes a POST /api/telemetry/diagnostic route that was never built. The fix track supplies the consent pieces: FIX:FINSEC-04 (kyc_consent_service.has_active_consent), FIX:FINSEC-09 (CONSENT_PURPOSES, plus policy_version and app_version on kyc_consents) and FIX:DB-10 (one active consent per type). FIX:FINSEC-03 supplies the erasure registry and FIX:PERF-15 the retention job. kyc_consent_service has three withdrawal paths (record_consent with granted=False, revoke_consent, and compliance_service.withdraw_consent, which calls revoke_consent). None of them touches data collected under the consent. analysis_jobs.user_id is client-supplied today, so events take identity only from the token. |
| 60 I46 Admin console v2 | partial | Simplify: built 'audit and flags' and nothing more. audit_now() records every user-level admin read and fails closed (drill-down, users list, analysis detail, AI-engine job list and detail, error telemetry). The polled AI-engine list is throttled to one row per admin and filter set per 15 minutes. platform-flags provides the project's flag mechanism with one registered key, 'analytics'. The Your Data rights surface is never switchable, the canary uses env, and the speculative value column is dropped. It uses the FEATURE_<KEY> env prefix that the other cluster plans use, so human step 2 can merge them into it. Flag changes are audited, and /api/v1/flags is no-store and varies by Authorization. Jobs, Audit and Usage pages are added to the same static console. There is no audit-actor schema migration: FINSEC-22 rows already store the actor in user_id, and the target goes in details JSON. Users are tombstoned, not deleted (FINSEC-03), so foreign keys stay valid. The aggregate /dashboard-data poll is not audited. Admin pages are protected by is_admin rather than a flag. | Already delivered by the fix track: FIX:AUTH-19 (static admin assets, esc() on every innerHTML, route-specific CSP; #688), FIX:GH-689 (pagination, lazy analysis detail; #689), FIX:REL-15 (routers/admin_dashboard.py and services/admin_dashboard_service.py), FIX:REL-16 and FIX:ARCH-05 (accurate dashboard state), FIX:AUTH-01 and FIX:AUTH-02 (users.is_admin, admin JWT login, no ADMIN_TOKEN), FIX:FINSEC-22 (services/audit_service.audit with request context) and FIX:REL-11 (admin-only SSE). Still missing: an audit row when an admin opens a user's data (dashboard-user-data, main.py:2344), and any flags page. No server-side flag mechanism exists; config/settings.py holds env constants only, and five other cluster plans each define their own flag module. The console polls GET /api/v1/dashboard/ai-engine every 10 s (main.py:1665, loadAIEngine), and that list carries user ids and tickers. |
| 56 I48 Leave the home server | partial | Simplify: C5 is the smaller version, and its one missing piece is built as a monthly automated restore drill. platform-restore-drill provides it and platform-scheduler-ist schedules it; it records a job_runs row and alerts on failure. A full restore only ever targets a scratch database: its name must contain 'drill' or 'scratch', and it may not match DATABASE_URL or any other *_DATABASE_URL. All of this is checked before any subprocess runs. The cloud move is deferred, as all five council members advised. CLOUD_MIGRATION.md documents the triggers: before billing goes live, partner due diligence, repeated outages, or a need for more than one API process. It also documents the target topology. | The smaller version is C5, and the fix track covers almost all of it. FIX:OPS-03 adds nightly SQLite and pg_dump backups kept outside the checkout (14 retained), a heartbeat, a pre-migration gate, and BACKUP_RESTORE.md with a quarterly manual drill. FIX:DB-14 handles the migration target and fails fast. FIX:OPS-06 makes systemd the only supervisor with exact-SHA checkouts, and FIX:OPS-10 deletes deploy.yml and pins actions. FIX:REL-08 and FIX:ARCH-07 run one worker without --reload. FIX:REL-18 adds a readiness probe, FIX:OPS-18 honours REDIS_URL (Redis was hard-coded at cache_service.py:49) and FIX:AUTH-20 binds to 127.0.0.1. Gap: C5's 'monthly restore drill into a scratch database with row-count checks' exists only as a manual checklist. No other cluster plan in this run builds a drill. |
| 28 I06 Privacy center: erasure, export, consent | partial | Simplify: the smaller version is fix-track work and is not re-planned. This cluster adds what the task's DPDP constraints still require. A JSON export is built from ORM metadata, so it grows with the schema. Each table is filtered on one owner column (EXPORT_OWNER_COLUMN for user_blocks), and other users' ids are set to null, so an export never reveals who blocked or reported the user. A 'Your Data' screen holds a stored-data notice that covers every exported table (a test enforces this), the export, the analytics toggle, and links to consents, the policy and FINSEC-03's delete sheet. An EXTRA_USER_COLUMNS registry, with a completeness test, is used by both erasure and export. Withdrawing analytics consent erases the events. A DPDP runbook covers rights handling, Rule 7 breach intimation, the retention schedule, and the Rule 8(3) one-year retention decision. No new consents table is needed, because kyc_consents already covers it. The export and the screen are not behind a flag: they are rights surfaces, like account deletion, so no switch can turn them off. They degrade through error states instead. | The smaller version, an in-app delete that removes holdings, transactions, alerts, device tokens and analyses, is FIX:FINSEC-03 (overlapping DB-06 and WIP-04). It covers the users.deleted_at tombstone, ERASURE_POLICY over every users.id foreign key with a CI metadata test, token rejection after deletion, and the iOS DeleteAccountSheet. Consent is also fix-track work. FIX:FINSEC-04 adds the ai_processing gate and prompt minimisation, which are the roadmap's routing rules for prompts that carry personal data. FIX:FINSEC-09 makes kyc_consents a versioned consents table. FIX:DB-10 fixes withdrawal, FIX:UX-30 adds confirmations to destructive rows, FIX:IOSCORE-26 and commit 9e95a06 add the privacy manifest, and FIX:FINSEC-22 adds the audit trail. 33 tables link to users, and user_blocks has two users foreign keys (blocker_user_id and blocked_user_id, db_models.py:1227-1228). Missing: any data export (DPDP s.11 access right; Rule 14 wants an in-app way to exercise rights) and one 'Your data' place. Also missing is erasure and export of user-linked columns that have no foreign key: research_reports.requested_by_user_id (ENG:be-db-ledger) and llm_usage.user_id (FIX:LLM-02). |

## Spec

# Cluster `platform`: platform, operations and privacy (implementation spec)

## 0. Summary

| # | Feature | Verdict | Status | Delta built by this cluster |
|---|---|---|---|---|
| 30 | I08 Observability baseline | Simplify | partial | `job_runs` history for every scheduled job, sync or async; alerts on first failure and on recovery; a daily model canary; a jobs section in the daily digest; an admin Jobs page |
| 32 | I09 One IST scheduler | Simplify | partial | Asia/Kolkata scheduler with explicit job ids; research jobs pinned to UTC; price alerts only during market hours; exactly-once and IST tests; tutorial copy |
| 46 | C12 Event loop | Build | partial | Ruff's flake8-async codes gated in CI with a shrink-only baseline, plus a small AST test for project blocking calls and for `await` on sync functions |
| 36 | I47 Product analytics | Simplify | new | `user_events`; consent-gated, allowlisted `POST /api/v1/events`; one neutral in-app ask; erasure on consent withdrawal; configurable retention (180 days by default); iOS EventLogger; admin Usage page; flag OFF |
| 60 | I46 Admin console v2 | Simplify | partial | Server flag mechanism and Flags page; audit row on every user-level admin read; Jobs, Audit and Usage pages |
| 56 | I48 Leave the home server | Simplify | partial | Monthly automated restore drill with row counts and scratch-database guards; cloud-move readiness doc. The move itself is deferred |
| 28 | I06 Privacy center | Simplify | partial | JSON export that never discloses other users; "Your Data" screen with a complete stored-data notice; user-linked columns without foreign keys added to erasure and export; DPDP runbook including the Rule 8(3) decision |

**Principles.**
- Fix-track and engine work is referenced as `FIX:`/`ENG:` and never re-planned.
- One table per concern. `job_runs` is the only persisted job-status table, because FIX:SILENT-13 is trimmed before its wave runs (human step 1) and never creates `scheduler_job_status`. No new consents table is created, because `kyc_consents` after FIX:FINSEC-09 and FIX:DB-10 already holds purpose, policy version, app version, granted_at and revoked_at.
- Identity always comes from the token.
- No new third-party runtime dependency. Only httpx, APScheduler, SQLAlchemy, the stdlib and Apple frameworks are used. Ruff is already pinned as a dev tool by FIX:TEST-14.
- Every new user-facing surface sits behind a server flag, with one deliberate exception. The data export and the "Your Data" screen are statutory rights surfaces (DPDP s.11 and Rule 14), like FINSEC-03's account deletion, so no switch may turn them off. They degrade through error states instead, and a faulty export is fixed with a backend hotfix. Admin-only pages are protected by `is_admin`. The model canary is an ops job switched by env.

**Build order.** Arrows run in sequence; ∥ means the two can run in parallel.
- Before any wave: trim FIX:SILENT-13 (human step 1) and merge the other clusters' flag modules into `platform-flags` (human step 2).
- Backend: `platform-flags` → `platform-jobruns` → (`platform-restore-drill` ∥ `platform-events-db`) → (`platform-scheduler-ist` ∥ `platform-events-api`) → `platform-privacy-export` → `platform-admin-api` → `platform-admin-ui` → `platform-async-guard`. The async guard goes last so its baselines see final code.
- iOS: `platform-ios-flags-events` → (`platform-ios-privacy-center` ∥ `platform-ios-event-callsites`).
- Land `platform-scheduler-ist` before other clusters add scheduler jobs, so their new jobs are written in IST from the start.

**Migration chain.** Each migration uses `down_revision` = the head at implementation time, and package dependencies serialise them: `ba5740a03b6b` (feature_flags) → `24a2a72cebb6` (job_runs) → `eaa69e058d9a` (user_events). Every migration is idempotent and uses the inspector pattern of `t4u5v6w7x8y9_add_research_engine_tables.py`. The upgrade/downgrade cycle runs in CI; locally, the `down_revision` graph is checked statically for a single head.

**Flags.** Resolution order is DB row, then env `FEATURE_<KEY>`, then the code default. The registry holds one key:

| Key | Default | Client-visible | Gates | When to flip |
|---|---|---|---|---|
| `analytics` | OFF | yes | Event storage, iOS EventLogger, the Home analytics ask, the Privacy Center analytics toggle | ON once the privacy policy names product analytics, its purpose, its retention and deletion on withdrawal (FIX:FINSEC-09 owner text). The App Store privacy label is updated in the submission that first ships EventLogger, whatever the flag state |

`analytics_consented` and `analytics_retention_days` are computed per request on `/api/v1/flags`. They are never stored as flags.

**Engine alignment.**
- Research flags stay env-only (engine decisions D27 and D36) and are not moved into `feature_flags`.
- Research cron windows are defined in UTC, because they start at :30 IST. They are pinned with `timezone="UTC"` inside the otherwise-IST scheduler.
- Events use the engine's vocabulary: `report_view` and `report_compute` replace analysis_start and analysis_view. Props never carry a ticker.
- The export includes the user's on-demand research requests, and erasure unlinks them.

---

## 1. Server-side feature flags (foundation for I46 and I47)

**User story.** As the owner I can switch a surface off or on for everyone without an App Store release, and I can see who changed it.

**Scope (v1).** One table, a code registry of known keys, a cached resolver, one public client endpoint, and admin read/write (§6).

**Data model.** `feature_flags`, migration `ba5740a03b6b`:

| Column | Type | Notes |
|---|---|---|
| `key` | String(64) | Primary key |
| `enabled` | Boolean | NOT NULL, default False |
| `updated_by` | Integer | NULL; admin id; no foreign key, so it needs no erasure entry |
| `updated_at` | DateTime | NOT NULL |

There is no `value` column. Non-boolean settings wait for a real consumer, and adding a nullable column then is a one-step migration.

**Backend.**
- `services/feature_flags.py` exposes `is_enabled`, `client_flags`, `list_flags`, `set_flag` and `_reset_cache`.
- Rows are cached for 30 s. A DB error falls back to env and defaults and never raises. Unknown keys resolve to False.
- Public endpoint `GET /api/v1/flags` (no auth) returns `{"flags": {"analytics": false, "analytics_consented": false}, "analytics_retention_days": 180}`. It sends `Cache-Control: no-store, private` and `Vary: Authorization`, because the body depends on the caller's token. The events package adds `analytics_consented` and `analytics_retention_days`. `analytics_consented` is true only with a valid token, the global flag ON, and an active `product_analytics` consent.
- If an auth-by-default middleware lands, `/api/v1/flags` must be on its public allowlist.

**Cross-cluster convergence.** Five other cluster plans each define their own flag module:
- data-flags and ai-flags: `core/feature_flags.py`, env `FEATURE_<KEY>`;
- the money plan: `core/feature_flags.py` with `require_flag`, reading `/api/v1/features`;
- habit-flags: `services/feature_flags.py` plus `GET /api/v1/features`;
- ios-flags-be: `config/feature_flags.py` plus `GET /api/v1/app-config`.

Six modules and three client endpoints cannot all ship. `platform-flags` is the superset: it uses the same `FEATURE_<KEY>` env prefix and the same `is_enabled` / `client_flags` names, and it adds the DB override that the admin Flags page needs. The other packages therefore reduce to `FLAG_DEFAULTS` entries (human step 2). The response shape `{"flags": {...}}` matches habit's, so whichever public path the integration lead keeps, clients change only the path.

**iOS.** `RemoteFlags` refreshes at boot, on foreground when the last fetch is older than 5 minutes, and on login change. It caches the last-known global flags and `analytics_retention_days` in UserDefaults. It never caches the per-user `analytics_consented`. Unknown keys read as false, so features stay hidden.

**Tests.** Defaults, env override, DB precedence, fail-closed unknown keys, immediate visibility after `set_flag`, DB outage fallback, and the public endpoint's body and cache headers.

**Risks.**
- Flag sprawl: the code registry with descriptions is the cap.
- Values can be up to 30 s stale. There is one process, and `set_flag` invalidates the cache.

## 2. I08 Observability baseline (smaller version: job_runs plus the canary)

**User story.** As the owner I learn within minutes that a nightly job failed or that a model id was retired, and I can see job history and success rate.

**Data model.** `job_runs`, migration `24a2a72cebb6`:

| Column | Type | Notes |
|---|---|---|
| `id` | Integer | Primary key |
| `job_name` | String(64) | |
| `status` | String(16) | CHECK `running`, `ok` or `failed` |
| `started_at` | DateTime | |
| `finished_at` | DateTime | NULL |
| `duration_ms` | Integer | NULL |
| `rows_written` | Integer | NULL |
| `error` | Text | NULL; scrubbed, 2,000 characters at most |
| `meta` | JSON | NULL |

Indexes are `(job_name, started_at)` and `(status, started_at)`. Datetimes are stored as naive UTC (FIX:DB-24) and serialised with a trailing `Z`.

**Relationship to FIX:SILENT-13.** SILENT-13 (wave p2-50, not yet run) plans three persistence pieces: a one-row-per-job `scheduler_job_status` table, `_persist_job_status`, and a dashboard read from that table. Its planned migration id `t4u5v6w7x8y9` is also already used by the engine's research-tables migration. Human step 1 trims all three before the wave runs. SILENT-13 keeps the module logger, the deletion of the two crashing cache jobs, `logger.exception` in every wrapper, and the in-memory `setdefault` for unknown dashboard keys. `job_runs` is then the only persisted job status. If p2-50 already ran untrimmed, `platform-jobruns` removes `scheduler_job_status` as a fallback.

**Backend.**
- `services/job_runs.py:tracked(name, fn)` writes a running row and runs the job.
  - A coroutine function gets an `async def` wrapper that awaits it, so the job stays on the scheduler's event loop. Its bookkeeping calls run through `asyncio.to_thread`, so DB writes and the alert POST never block the loop. Any other callable gets a sync wrapper. There is no `asyncio.run` path.
  - On success it records ok, duration and rows.
  - On an exception it records failed with the error scrubbed (email, PAN, Bearer tokens, URL credentials and 10+ digit runs are masked), then re-raises.
  - Bookkeeping failures never block the job.
- `platform-scheduler-ist` wraps the scheduler's `add_job`, so every job is tracked, including `register_research_jobs` and any job other clusters add later. Wrappers that swallow exceptions gain a bare `raise`, so failures are recorded truthfully.
- **Alerts** go to FIX:OPS-14's `OPS_ALERT_WEBHOOK_URL` (ntfy-compatible).
  - "Nivesh job failed: X" is sent only for the first failure in a streak. The body is the scrubbed error, capped at 300 characters.
  - "Nivesh job recovered: X" is sent on the next ok run.
  - Running rows left by a restart become failed ("abandoned: scheduler restarted"), with no alert.
  - The relay is a data processor. The export's processor list and the DPDP runbook list it as "Operations alert relay (owner-chosen): scrubbed error text only". OBSERVABILITY.md recommends a self-hosted ntfy server or an access-controlled topic, because anyone who knows a public ntfy.sh topic's name can read it.
- The **daily digest** (FIX:SILENT-17/OPS-14) gains a "Scheduled jobs (last 24h)" block. If the query fails it prints UNKNOWN instead of a clean result.
- **Retention:** `run_retention` (FIX:PERF-15) purges job_runs rows older than 90 days at 03:15 IST.
- **Canary**, `services/model_canary.py`, runs daily at 08:30 IST.
  - It sends a one-token request through the gateway to each model id in `llm_utils` (DEEPSEEK_MODEL, HAIKU_MODEL, SONNET_MODEL) plus any in `CANARY_EXTRA_MODELS`.
  - Env `CANARY_ENABLED` (default on) switches it off when all LLM spend must be zero. It is an ops job, so it is not a server flag.
  - A missing API key gives `skipped_no_key`. A budget breaker gives `skipped_budget`, which is not a failure.
  - Any other error raises `CanaryFailure("models failing: …")`. `tracked` records it and alerts.
- **Admin:** the Jobs page is described in §6.

**Deferred** (documented in OBSERVABILITY.md):
- `/api/v1/data-status` and user-facing "as of" footers. Engine reports already carry staleness; when a screen needs these, read `job_runs.latest_by_job()`.
- Merging the four `*_error_logs` tables.
- GlitchTip and crash upload, which need consent and a new dependency.
- Missed-run detection. OPS-03's backup heartbeat already catches a dead scheduler.
- A thread-pool size knob. If `/health` latency rises while the CPU is idle (thread starvation), raise AnyIO's default thread limiter at startup. Nothing is built until a measurement shows the need.

**Tests.**
- Success and failure rows; re-raise.
- An async job's wrapper stays a coroutine function and records both ok and failed rows.
- Scrubbing; the 300-character alert cap.
- Bookkeeping outage does not stop the job.
- Alert streak rule and recovery alert.
- `mark_abandoned`; summary percentages; pagination; purge.
- The digest section.
- The canary's outcome matrix.

**Risks.**
- Alert fatigue: mitigated by alerting only on a streak's first failure and on recovery.
- PII in errors: mitigated by scrubbing, the length caps, and a private alert topic.
- Table growth is about 2,000 rows a week: price alerts 84 per weekday, research polls about 96 a day, six 2-hour interval jobs 72 a day, the hourly anomaly scan, and about 15 daily jobs. That is about 25,000 rows at the 90-day purge.

## 3. I09 One IST scheduler (smaller version: no separate process)

**User story.** As the developer I read and write schedules in IST, the time the business runs on. Price alerts run only while the market is open, and every job runs exactly once.

**Changes** (`services/harvest_worker.py`, after the fix track and ENG:be-wiring):
- The scheduler is built as `AsyncIOScheduler(timezone="Asia/Kolkata", job_defaults=<FIX:REL-03 values>)`.
- Every `add_job` gets an explicit `id=`.
- Cron fields are converted from UTC to IST wall clock by adding 05:30. If the result crosses midnight, `day_of_week` moves forward one day. Interval jobs are unchanged.
- The leader calls `job_runs.mark_abandoned()` once at start.
- `services/research/jobs.py` passes `timezone="UTC"` on its 7 cron jobs and leaves their fields unchanged.

| id | Old (UTC field) | New (IST field) | Source |
|---|---|---|---|
| advisor_harvest | 01:30 | 07:00 | existing |
| morning_brief_pregen | 01:00 | 06:30 | existing (the habit cluster may replace it) |
| error_digest | 01:30 | 07:00 | existing |
| model_canary | — | 08:30 | new |
| price_alerts | every 5 min, all day | Mon–Fri 09:00–15:55, every 5 min | FIX:REL-09 plus this package |
| portfolio_snapshot | 11:00 | 16:30 | existing |
| nightly_screen | 11:15 | 16:45 | existing |
| bhavcopy | 13:30 | 19:00 | existing (the data cluster may replace it) |
| piotroski_weekly | Sun 17:30 | Sun 23:00 | existing |
| legacy_outcome_eval | 20:30 | 02:00 | existing, until engine Stage 3 |
| db_backup | 21:00 | 02:30 | FIX:OPS-03 |
| prediction_outcomes | 21:00 | 02:30 | FIX:ML-03 |
| notification_cleanup | 21:30 | 03:00 | existing |
| preferences_backfill | 21:35 | 03:05 | existing |
| rag_ingest | 21:45 | 03:15 | FIX:REL-21 |
| retention | 21:45 | 03:15 | FIX:PERF-15 |
| deletion_requests | 22:00 | 03:30 | only if FIX:DB-06's grace-period job exists |
| restore_drill | — | day 1, 04:00 | new |
| anomaly_scan | hourly at :00 | hourly at :00, or FIX:PERF-19's time converted | existing |
| news_harvest, youtube_metadata, youtube_portfolio, expert_harvest, sebi_harvest, youtube_expert_harvest | 2 h interval | unchanged | existing |
| research_* (7 jobs) | UTC | still UTC, pinned. IST equivalents: kick Mon–Fri 19:45 and 21:00 and Tue–Sat 07:15; poll every 5 min 06:30–09:25 and 19:30–00:25; score Mon–Fri 22:30; live metrics Sun 10:00; cleanup 02:30 | ENG:be-ingest-jobs |

**Not built** (owned elsewhere or deferred):
- Filings scheduling (I31/C15) and the AMFI NAV harvest (I16) belong to other clusters.
- Outcomes are scored by the engine's `research_score_outcomes` (plus FIX:ML-03 for the legacy ledger).
- Celery deletion, the crashing-job fixes and the leader-only poller are FIX:REL-12, FIX:SILENT-13 and FIX:REL-09.
- RAG ingestion runs in the worker under FIX:REL-21.
- The separate worker process is deferred; see CLOUD_MIGRATION.md.

**iOS copy.** Tutorial step 8 becomes: "Set a price alert for any stock. While the market is open we check your alert prices every 5 minutes and notify you when one is crossed." The old "target price" wording is research-call vocabulary under the SEBI RA amendments, so it is dropped.

**Docs.** `docs/codebase/SCHEDULER.md` holds the table above and the rules for new jobs:
- Use IST wall clock. Use `timezone="UTC"` only for windows defined in UTC.
- Always pass `id=`.
- Write jobs as plain `def` that raise on failure.
- Tracking is automatic, for sync and async jobs alike.

**Tests.**
- The constructor timezone is Asia/Kolkata. Every job has a unique id, and every registered function carries `_job_runs_name`.
- Each expected IST wall-clock time is checked by computing the next fire time from Monday 2026-10-12 00:00 IST.
- `price_alerts` next fires on Monday 09:00 when checked from Saturday 10:00, and on Tuesday 09:00 when checked from Monday 15:56.
- Research cron triggers are UTC; `mark_abandoned` runs once.
- The morning-briefing tests are updated: timezone is Asia/Kolkata, pregen runs at 06:30, and B2 checks for `timezone="Asia/Kolkata"`.

**Risks.**
- Double-shifted times: guarded by the table test.
- Other clusters' jobs: covered by the SCHEDULER.md rule and by landing this package early.
- Several jobs at 02:30 IST: acceptable, because the SQLite backup API and pg_dump take consistent snapshots.

## 4. C12 Stop blocking the event loop (Build: add the missing rule)

**User story.** As the developer I cannot reintroduce a blocking call into the event loop without CI telling me.

**Ruff.** FIX:TEST-14 pins ruff 0.8.6 and gates `--select E9,F63,F7,F82` in `backend_ci.yml`. This cluster appends the flake8-async codes for blocking I/O in `async def`:
- ASYNC210: blocking HTTP;
- ASYNC220, ASYNC221 and ASYNC222: subprocess;
- ASYNC230: `open`;
- ASYNC251: `time.sleep`.

Existing hits are baselined as `[lint.per-file-ignores]` in a new `backend/ruff.toml`; entries may only be removed. Ruff covers every backend module, including `services/`, where AsyncIOScheduler jobs and copilot code run on the API loop. The implementer computes the baseline with ruff 0.8.6 installed in a scratch venv; ruff is a standalone linter and never imports backend code.

**AST test.** `backend/tests/test_async_hygiene.py` uses only stdlib `ast` and covers what ruff cannot know.
- **Check 1, project blocking calls.** It looks inside every `async def` in `routers/`, `core/`, `middleware/`, `services/` and `main.py`. It flags a call that resolves through the module's imports to `get_session`, `deepseek_chat`, `claude_messages`, `claude_haiku`, `yfinance.download` or `yfinance.Ticker`. Nested defs and lambdas are excluded. A function passed to `asyncio.to_thread`, `run_in_threadpool` or `run_in_executor` is an argument, not a call, so it passes.
- **Check 2, `await` on a sync function** (the portfolio_snapshot.py:232 bug class). The callee is resolved precisely, never by matching a bare name across the backend. It is one of:
  - (a) a bare name defined at module level in the same file, or imported with `from <backend module> import f [as g]`;
  - (b) `self.m()`, where `m` is defined in the enclosing class;
  - (c) `mod.f()`, where `mod` is an import alias of a backend module.

  Every other attribute call is skipped, for example `await request.json()`, `await client.get()` and `await websocket.send_text()`. A call is flagged when the resolved definition is a plain `def`.
- A trailing `# async-ok: <reason>` comment on the line suppresses a finding, so justified new code never needs the baseline to grow.
- The baseline is a frozenset literal, computed at implementation time with a scratch copy of the scanner that only parses files. It can only shrink: new findings fail the test, and so do baseline entries that no longer occur.

**Not built.**
- An async LLM gateway. REL-01 decided that every LLM caller is sync and runs in the threadpool, and Check 1 keeps sync LLM calls out of `async def`.
- The thread-pool knob, which is deferred (§2).

**Tests.**
- Scanner unit cases on inline source strings.
- The repository-wide no-new-violations and stale-baseline tests.
- The ruff gate in CI.
- FIX:REL-01's test (b) and FIX:PERF-02's test (a) already check that a slow handler does not block /ping or /health/live.

## 5. I47 First-party product analytics (the ten events)

**User story.** As the owner I can measure activation, retention and funnels without a third-party SDK and without collecting what users hold.

**Consent and flag.**
- The consent is opt-in, type `product_analytics`, stored in `kyc_consents` and checked by the server on every batch with FIX:FINSEC-04's `has_active_consent`.
- `CONSENT_PURPOSES['product_analytics']` is added for FIX:FINSEC-09. Its text states the retention period and that turning analytics off deletes recorded events.
- **One in-context ask.** A toggle three screens deep would collect almost no consent, and funnels from a dozen users are noise.
  - So, once per user per device, a neutral card at the top of Home asks "Help improve Nivesh?". It shows the purpose text and two equal-weight buttons, "Allow" and "Not now".
  - Nothing is pre-selected. "Not now" records nothing and the card never returns. The toggle in Your Data stays available.
  - This is free, specific, informed and unambiguous consent (DPDP s.6), and it does not pressure the user (App Store 5.1.1).
  - The card shows only while `analytics` is ON, the user is logged in, and they have not consented.
- **Withdrawal erases.** Turning the consent off calls `events_service.erase_user_events(user_id)` after the withdrawal commits, so the erase never blocks or undoes the withdrawal (DPDP s.6(4)-(6), s.8(7)).
  - This applies to every path: `record_consent(granted=False)`, `revoke_consent` and `compliance_service.withdraw_consent`.
  - The daily retention step also deletes the events of every user without an active `product_analytics` consent. A failed immediate erase is therefore cleaned up within a day.
- **Retention.** `USER_EVENTS_RETENTION_DAYS` (env, default 180) drives the purge, the purpose text and the iOS caption, which is served as `analytics_retention_days`. DPDP Rules 2025 Rule 8(3) may require one year; the runbook records the decision (§7).
- Only logged-in users who consented are counted. App Store Connect analytics remains the unbiased baseline.
- Flag `analytics` stays OFF until the privacy policy names analytics.

**Event allowlist** (server `services/events_service.py:EVENT_SCHEMA`). Props are optional, use only the listed values, and carry at most 4 keys.

| Event | Fired when | Props |
|---|---|---|
| app_open | app becomes active (after flags refresh) | launch: cold \| warm |
| search | a debounced search returns | results: 0 \| 1-5 \| 6+ |
| stock_view | stock page appears | — |
| report_view | a stock report state is shown | state: fresh \| stale \| expired \| not_covered \| unavailable |
| report_compute | on-demand compute finishes | result: ok \| quota \| unavailable \| error |
| alert_create | a price alert is saved | direction: above \| below |
| import_start | an import starts (money cluster CAS) | kind: cas \| csv \| manual |
| import_done | an import finishes (money cluster) | kind: as above; outcome: ok \| partial \| failed |
| paywall_view | paywall appears | — |
| purchase | a StoreKit purchase finishes (growth cluster) | outcome: success \| cancelled \| failed \| pending |

**Data model.** `user_events`, migration `eaa69e058d9a`:

| Column | Type | Notes |
|---|---|---|
| `id` | Integer | Primary key |
| `user_id` | Integer | Foreign key to users, NOT NULL |
| `event_name` | String(40) | |
| `props` | JSON | |
| `app_version` | String(20) | |
| `platform` | String(10) | default `ios` |
| `created_at` | DateTime | Client time, clamped to [now − 7 days, now + 5 minutes] |

- Indexes are `(event_name, created_at)` and `(user_id, created_at)`.
- There is no DB CHECK on `event_name`: the allowlist lives in code, and a CHECK would need a migration for every new event.
- ERASURE_POLICY marks the table `delete`, and the export includes it.
- Retention runs at 03:15 IST. It purges rows older than `USER_EVENTS_RETENTION_DAYS`, and the rows of users with no active consent.

**API.**
```
POST /api/v1/events          Authorization: Bearer (401 otherwise)
{"events": [{"name": "app_open", "props": {"launch": "cold"}, "ts": "2026-10-11T03:12:00Z"}],
 "app_version": "1.4.0", "platform": "ios"}                 1..50 events, else 422
202 {"accepted": 1, "rejected": 0, "reason": null}          reason: null | "disabled" | "no_consent"

GET /api/v1/flags            (token optional)
200 {"flags": {"analytics": true, "analytics_consented": true}, "analytics_retention_days": 180}
    Cache-Control: no-store, private; Vary: Authorization
```
- The user id comes only from the token.
- The rate limit is 120 requests per hour per user, under the key `events`. The key has no leading slash, so the per-IP middleware never matches it.
- Invalid events are counted in `rejected` and never stored.

**iOS.**
- `EventLogger` keeps an in-memory buffer capped at 200. It flushes at 20 events or when the app goes to the background, in batches of at most 50.
- It runs only when `analytics` and `analytics_consented` are on and a token exists.
- A `no_consent` or `disabled` reply clears the buffer and refreshes flags.
- Call sites:
  - app_open, search, stock_view, alert_create and paywall_view;
  - report_view and report_compute, in the engine's ResearchReportView;
  - import_* and purchase are logged by the money and growth packages using the same enum.
- The Home ask is `AnalyticsConsentCard`; the toggle lives in the Privacy Center (§7). Both show the caption with the server's retention days.
- `PrivacyInfo.xcprivacy` declares ProductInteraction: linked to the user, not used for tracking, purpose Analytics. The App Store privacy label is updated in the same submission (human step 3).

**Queries.** `docs/analytics/QUERIES.md` has Postgres SQL for:
- DAU and WAU;
- D1/D7/D30 cohort retention;
- search → stock_view → report_view;
- paywall → purchase;
- the compute outcome mix.

The admin Usage page shows daily counts by IST date and the number of active users with analytics on.

**Tests.**
- 401 without a token; flag off; no consent; storage under the token's user even when the body carries another id.
- Unknown event, unknown prop and bad value are rejected; 51 events gives 422.
- Timestamp clamping; 429; `analytics_consented` logic; IST date bucketing; `active_users`.
- Withdrawal: grant consent, ingest 3 events, revoke, and 0 rows remain and `daily_counts` excludes the user. The same holds through `record_consent(granted=False)` and through `withdraw_consent`. When the erase fails, the withdrawal still succeeds.
- Retention purges old rows and the rows of users without consent.
- The flags payload carries the retention days and the cache headers.
- iOS: EventLogger buffering, flushing and consent handling, the request headers and body, the caption and the once-per-user ask.

**Risks.**
- DPDP purpose limitation: analytics only, documented in the purpose text and the runbook.
- Sampling bias: only consented users are counted; the in-context ask enlarges the sample without pressure.
- Scope creep: every new event is a reviewed allowlist change.
- Rule 8(3): if legal adopts the one-year reading, set `USER_EVENTS_RETENTION_DAYS=365`. Withdrawal then marks events as withdrawn and excludes them from every query instead of deleting them (runbook).

## 6. I46 Admin console v2 (audit and flags)

**User story.** As the owner I can see and switch flags, read job health and usage, and know that every look at a user's data leaves an audit row.

**Admin API.** Routes live in `routers/admin_ops.py`. All of them require `require_admin` (`users.is_admin`, FIX:AUTH-01) and are plain `def`.
```
GET  /api/v1/admin/flags                          -> {"flags":[{"key","enabled","default","source":"db|env|default","client_visible","description","updated_by","updated_at"}]}
PUT  /api/v1/admin/flags/{key}  {"enabled": true} -> {"flag": {...}} | 404 Unknown flag   (audit admin_flag_changed {key,from,to})
GET  /api/v1/admin/job-runs?job_name=&status=&limit=50&before_id= -> {"runs":[{"id","job_name","status","started_at","finished_at","duration_ms","rows_written","error"}],"next_before_id":null}
GET  /api/v1/admin/job-runs/summary?days=7        -> {"days":7,"overall_success_pct":99.2,"jobs":[{"job_name","runs","failures","success_pct","last_status","last_started_at","last_error"}]}
GET  /api/v1/admin/audit?action_prefix=admin_&limit=100&before_id= -> {"entries":[{"id","actor_user_id","action","details","created_at","ip_address"}],"next_before_id":..}
GET  /api/v1/admin/analytics/daily?days=14        -> {"days":14,"active_users":12,"rows":[{"date":"2026-10-10","event_name":"app_open","events":40,"users":9}]}
```

**Audit hooks.** `audit_service.audit_now` is added to FIX:FINSEC-22's module. It fails closed: if the audit row cannot be written, the request fails and returns no data.

| Read | Action | Details |
|---|---|---|
| `GET /dashboard-user-data` | `admin_viewed_user` | `{target_user_id}` |
| `GET /dashboard-data/analysis/{id}` | `admin_viewed_analysis` | `{analysis_id}` |
| `GET /users` | `admin_listed_users` | — |
| `GET /api/v1/admin/error-telemetry` | `admin_viewed_error_telemetry` | — |
| `GET /api/v1/dashboard/ai-engine` | `admin_listed_jobs` | `{filters}`; at most one row per admin and filter set per 15 minutes |
| `GET /api/v1/dashboard/ai-engine/{job_id}` | `admin_viewed_job` | `{job_id}` |

- The console polls the AI-engine list every 10 s (`loadAIEngine`, main.py:1665). Auditing every call would write 360 rows an hour, so the list uses `audit_now(..., min_interval_s=900)`. This is a per-process throttle, correct for the single worker of FIX:REL-08.
- The aggregate `/dashboard-data` poll and the audit list itself are not audited.
- The actor is the audit row's `user_id` and the target goes in details JSON, so no schema change is needed. Audit rows are kept for at least a year (DPDP Rules 6 and 8(3)).

**UI.** The static console from FIX:AUTH-19 and FIX:REL-15 gains Flags, Jobs, Audit and Usage tabs.
- All rendering goes through `esc()`, with delegated `data-action` handlers and no inline handlers.
- A flag toggle asks `confirm()` first.
- Usage shows "Active users with analytics on".

**Tests.**
- Every new route returns 401 without a token and 403 for a non-admin.
- A flag change flips the flag and writes one audit row; an unknown key gives 404.
- Pagination and summary over seeded rows.
- Each audited read writes exactly one row, and an audit failure gives 500 with no data.
- Two list polls within 15 minutes with the same filters write one row.
- Static UI checks.

**Risks.**
- Scope creep: limited to these four pages.
- Audit fail-closed can block admin reads during a DB outage. That is acceptable, because the reads would fail anyway.

## 7. I06 Privacy center (export and "Your Data")

**User story.** As a user I can see what Nivesh stores, download it, control analytics, reach my consents and policy, and delete my account, all from one screen.

**Export contract.**
```
GET /api/v1/compliance/my-data     Bearer required; not behind a flag
200 application/json; Content-Disposition: attachment; filename="nivesh-my-data-2026-10-11.json"; Cache-Control: no-store
{"schema_version":"nivesh-export.v1","generated_at":"…Z",
 "user":{"id":7,"username":"…","display_name":"…","created_at":"…Z"},
 "tables":{"portfolio":{"group":"Holdings, transactions, …","rows":[…],"truncated":false}, "user_blocks":{…}, "user_events":{…}, "research_reports":{…}, …},
 "purposes":{…CONSENT_PURPOSES…},
 "processors":[{"name":"DeepSeek","country":"PRC","purpose":"AI text, only with AI processing consent","data":"tickers, company names, percentage moves, chat text"}, …,
               {"name":"Operations alert relay (owner-chosen)","data":"scrubbed error text only"}],
 "notes":["Backups keep data up to 14 days after deletion", "Consent and audit records are kept after deletion without IP", "Usage events are deleted when you turn usage analytics off"]}
404 only when the account is missing or deleted; 429 after 5 exports in 24 h (key privacy_export); 401 without a valid token
```
- **Which tables.** Tables are found from ORM metadata. Every table with a foreign key to `users.id` is included, plus the columns listed in `EXTRA_USER_COLUMNS`.
- **One owner column per table.** Rows are selected on the table's owner column only, never on "any user column".
  - The owner column is the `EXPORT_OWNER_COLUMN` entry (`{'user_blocks': 'blocker_user_id'}`), or else the table's single user column.
  - Every other user-id column is set to null in the output. A user therefore never learns who blocked them, and a blocker's export shows the block without the blocked user's id.
  - A table with two or more user columns and no entry fails the completeness test, and it is skipped at runtime.
- Each table returns at most 5,000 rows, newest first. Strings are cut at 20,000 characters and binary values are omitted.
- `password_hash`, `token_version` and `refresh_token_hash` are dropped. Columns named `token` or `*_token` keep only their last 4 characters.
- Every export writes a `data_exported` audit row.
- **Stored-data notice.** Each exported table maps, through `TABLE_GROUPS`, to one of the seven "WHAT WE STORE" rows below. A test fails for any unmapped table, so the screen stays complete as the schema grows.

| Row (exact copy) | Tables |
|---|---|
| Your account: username, display name, settings and subscription | users, user_preferences, user_subscriptions |
| Holdings, transactions, watchlists, alerts and journal notes you add, and the values and tax reports we calculate from them | portfolio, portfolio_groups, portfolio_transactions, multi_asset_transactions, watchlists, price_targets, earnings_alerts, trade_journal, dividend_ledger, tax_reports, portfolio_valuation_history, net_worth_ledger |
| Loan, deposit, bank-account and finance-tracker records, if you use those features | linked_bank_accounts, loan_applications, loan_disbursements, fixed_deposit_bookings, finance_tracker_accounts |
| Posts, votes, reports and blocks in the community forum | forum_threads, forum_posts, forum_votes, forum_reports, user_blocks |
| Your device ID and push token, your consent choices and security records, with the IP address on them | device_tokens, device_bindings, device_binding_attempts, kyc_consents, audit_log_entries, data_deletion_requests |
| Your notifications, analyses and AI research requests | in_app_notifications, analysis_history, analysis_jobs, research_reports, llm_usage |
| Usage events, only if you turn on usage analytics | user_events |

**Erasure gap.** `compliance_service.EXTRA_USER_COLUMNS` lists `research_reports.requested_by_user_id` and `llm_usage.user_id` with policy `null_user`. `erase_user` (FIX:FINSEC-03) applies it. A completeness test fails for any new `*user_id` column that has no foreign key and is not registered.

**Screen.** `PrivacyCenterView` is pushed from Settings → DATA & PRIVACY → "Your Data". The row shows whenever the user is logged in. The view has no NavigationStack of its own, takes colours from Theme only, and every helper is a View struct. Use these texts exactly:
- **WHAT WE STORE**: the seven rows in the table above, in that order.
  - Footer: "AI features send stock names and percentage moves to our AI providers only if you allow AI processing."
- **DOWNLOAD A COPY**: "Get a file with the data linked to your account." Button "Prepare my data file".
  - While preparing: "Preparing your file…"
  - When ready: ShareLink "Save or share file"
  - Offline: "You're offline. Connect and try again."
  - 429: "You've downloaded your data several times today. Try again tomorrow."
  - 404: "Data download isn't available right now."
  - Any other error: "Couldn't prepare your file. Try again."
- **USAGE ANALYTICS**, shown only when `analytics` is on: toggle "Share usage analytics".
  - Caption: "Tells us which screens and features are used. We never record your holdings, stock names or amounts. Kept for N days. You can turn this off at any time; turning it off deletes what was recorded." N is the server's `analytics_retention_days`. If that is unknown, the sentence reads "Kept for the period set out in our Privacy Policy."
  - Error: "Couldn't update this setting. Try again."
  - The toggle reverts on failure.
- **Links**:
  - "AI processing and other consents" opens AccountSecurityView.
  - "Privacy Policy" opens DisclosureDetailView(.privacyPolicy).
  - "Delete account" (Theme.bearRed) presents FIX:FINSEC-03's DeleteAccountSheet.

**Home ask card** (`AnalyticsConsentCard`, §5): heading "HELP IMPROVE NIVESH", the same caption, and buttons "Allow" and "Not now" with identical styling.

The exported file is written to a temporary location with `.completeFileProtection`, and the previous export file is removed first.

**Runbook.** `docs/compliance/DPDP_RUNBOOK.md` covers:
- **Dates.** The Rules are G.S.R. 846(E), notified 13 Nov 2025. Rules 3, 5-16, 22 and 23 (including 6, 7, 8 and 14) fall in the 18-month tranche and apply from 13 May 2027. MeitY has proposed shortening that window: 12 months would mean 13 Nov 2026. Nothing has been notified as of Oct 2026; check the Gazette.
- **Rights handling:** access, correction, erasure, consent withdrawal (analytics events are erased immediately and by the daily backstop), and grievances.
- **Breach response under Rule 7.** Tell affected users and the Data Protection Board without delay, then send the detailed report to the Board within 72 hours of becoming aware. Includes an incident-log template.
- **Rule 8(3) decision.** The rule requires a fiduciary to keep personal data, associated traffic data and processing logs for at least one year from processing, for the Seventh Schedule purposes, and then erase them unless another law requires retention. Commentators read it two ways:
  - Narrow: the floor binds only processing for Seventh Schedule purposes. Usage events keep 180 days and are erased on withdrawal, as built.
  - Broad: a one-year floor for all personal data and logs. Set `USER_EVENTS_RETENTION_DAYS=365`, and on withdrawal mark events withdrawn and exclude them from every query instead of deleting them until the year has passed.

  Either way, audit_log_entries and access logs are kept for at least one year, including the rows of users erased under FINSEC-03. The owner and legal record the choice and its date here.
- **Retention schedule:**
  - user_events: `USER_EVENTS_RETENTION_DAYS` (180 days by default), and erased on withdrawal;
  - job_runs: 90 days;
  - news: 90 days;
  - backups: 14 days;
  - audit log and access logs: at least 1 year (Rules 6 and 8(3));
  - consents: kept.
- **Processors:** the list, including the operations alert relay.

**Tests.**
- The export contains the user's own rows and no one else's.
- Blocks: user B blocks user A. A's export has no `user_blocks` rows and no user-id value equal to B's id. B's export has the block, with `blocked_user_id` null.
- Secrets are absent, tokens masked, long strings truncated and the row cap respected.
- Every table with a users foreign key exports without error.
- The export works with no flag rows at all; the sixth export gives 429. The audit row and the attachment header are present.
- Completeness guards: unregistered non-FK user columns; multi-user-column tables without an owner; tables without a stored-data row; the seven strings present in PrivacyCenterView.swift (skipped when that file is absent).
- `erase_user` nulls the extra columns.
- iOS: view-model export and toggle states, the caption, and the per-user ask store.

**Risks.**
- Export size: capped per table.
- Data left in backups after erasure: disclosed, and rotated out after 14 days.
- Legal text and the Rule 8(3) reading: owner steps.

## 8. I48 Leave the home server (C5 gap and readiness doc)

**User story.** As the owner I know every month that last night's backup actually restores and holds the data I expect. I know exactly when and how to move off the home box.

**Drill.** `services/restore_drill.run_restore_drill()` runs monthly on day 1 at 04:00 IST (id `restore_drill`). `scripts/restore_drill.py` runs it by hand.
- It picks the newest main-database backup written by FIX:OPS-03.
- **SQLite:** copy it to a temp directory, require `PRAGMA integrity_check = ok`, then count rows.
- **Postgres:**
  - `pg_restore --list` always runs.
  - When `RESTORE_DRILL_PG_URL` (a scratch database) is set, a full `pg_restore --clean --if-exists --no-owner` runs into it, followed by row counts.
  - Before any subprocess runs, the code checks the target and raises `ValueError` without logging the URL. It refuses a database name that lacks "drill" or "scratch". It also refuses a host, port and database that match `DATABASE_URL` or any other configured `*_DATABASE_URL`, such as the harvester or RAG Postgres.
  - When the URL is unset, the status is `listed_only`.
- **Checks** compare row counts with the live DB for users, portfolio, portfolio_transactions, kyc_consents, audit_log_entries, research_predictions and job_runs. The drill fails when the backup holds less than 50% of a live table with at least 100 rows, or when users or transactions are empty in the backup but not live.
- The result is recorded in job_runs and alerts on failure.

**Docs.**
- `BACKUP_RESTORE.md` gains a monthly-drill section, including the scratch-database naming rule.
- `CLOUD_MIGRATION.md` records:
  - status: deferred;
  - triggers: before billing, partner due diligence, two outages of more than 4 hours in a month, or a need for more than one API process or host;
  - what is already portable;
  - the target: managed Postgres with point-in-time recovery and Redis in an Indian region, 1–2 API VMs, one worker VM, staging, and an iOS staging URL;
  - code needed at move time: a scheduler switch out of the API process, because the fcntl lock works only on one host; Redis-backed limits (FIX:ARCH-07); pool sizing (FIX:PERF-21);
  - a cutover and rollback outline.

**Tests.**
- Healthy, truncated, corrupt and missing backups.
- Each scratch-URL refusal (bad name, equal to live, equal to another `*_DATABASE_URL`) raises before any subprocess runs.
- Missing `pg_restore`.
- The CLI records a job_runs row.

## 9. Package test matrix

| Package | Tests (hermetic unless noted) |
|---|---|
| platform-flags | `tests/test_feature_flags.py` |
| platform-jobruns | `tests/test_job_runs.py`; `tests/test_scheduler_jobs.py` only if SILENT-13 ran untrimmed |
| platform-scheduler-ist | `tests/test_scheduler_ist.py`, `tests/test_model_canary.py`, updated morning_briefing tests |
| platform-async-guard | ruff ASYNC gate in `backend_ci.yml`; `tests/test_async_hygiene.py` |
| platform-events-db | `tests/test_user_events_model.py` |
| platform-events-api | `tests/test_events_api.py` |
| platform-privacy-export | `tests/test_privacy_export.py` |
| platform-admin-api | `tests/test_admin_ops.py` |
| platform-admin-ui | `tests/test_admin_ui_static.py` |
| platform-restore-drill | `tests/test_restore_drill.py` |
| platform-ios-flags-events | `stockmeTests/RemoteFlagsTests.swift`, `stockmeTests/EventLoggerTests.swift` |
| platform-ios-privacy-center | `stockmeTests/PrivacyCenterViewModelTests.swift` |
| platform-ios-event-callsites | `swiftc -parse`; grep acceptance checks |

**Local checks:**
- AST parse and pyright for Python;
- `swiftc -parse` for Swift;
- a static single-head check of `migrations/versions`;
- ruff 0.8.6 from a scratch venv for the ASYNC baseline.

Alembic cycles and full test suites run in CI.

## 10. Cluster risks

- **Ordering against fix-track edits** to harvest_worker.py, main.py, retention.py, kyc_consent_service.py and compliance_service.py. Every package names the expected post-fix state, and the dependencies serialise shared files.
- **Six flag mechanisms across cluster plans.** They are merged into platform-flags before any of them builds (human step 2).
- **SILENT-13 overlap.** It is trimmed before p2-50 runs (human step 1), and platform-jobruns has a fallback if it was not.
- **New user-linked tables from other clusters** must add a `TABLE_GROUPS` line, plus an `EXPORT_OWNER_COLUMN` entry when they have two user columns (for example a referral table). The export tests name the table. FINSEC-03's ERASURE_POLICY test already imposes the same discipline.
- **HomeScreen.swift is shared** with other clusters' Home sections. The ask card is a one-line insertion at the top of the main VStack.
- **Rule 8(3) is unresolved.** The build implements the narrow reading. Switching readings is an env value plus one code path.
- **Analytics stays dark** until the owner updates the legal text and flips the flag. That is intended.

## 11. Human and ops steps

See `human_steps`. In short:
- Trim SILENT-13 and merge the flag modules before the waves.
- Update the App Store privacy label with the first EventLogger build. Turn analytics on only after the policy text.
- Legal review of the runbook and the processors; the Rule 8(3) decision and its date.
- Keep logs for at least a year.
- Use a private alert topic.
- Set up the restore-drill scratch DB with a drill/scratch name.
- Check fire times after the IST switch.
- Admin account and CSP check.
- Canary model list.
- Approve the cloud-move triggers.

## Sources
- [MediaNama: data breach reporting timeline of the DPDP Rules 2025](https://www.medianama.com/2025/11/223-data-breach-reporting-timeline-of-dpdp-rules-2025-explained/)
- [DPDP Rules, Rule 7 (dpdpa.com)](https://www.dpdpa.com/dpdparules/rule7.html)
- [DPDP Rules, Rule 8 (dpdpa.com)](https://dpdpa.com/dpdparules/rule8.html)
- [MYND DPDP wiki: Rule 7, intimation of personal data breach](https://dpdp.myndsolution.com/wiki/rules/rule-7-intimation-of-personal-data-breach/)
- [MYND DPDP wiki: Rule 8, time period for specified purpose](https://dpdp.myndsolution.com/wiki/rules/rule-8-time-period-for-specified-purpose-to-be-deemed-as-no-longer/)
- [MYND DPDP wiki: Rule 14, rights of data principals](https://dpdp.myndsolution.com/wiki/rules/rule-14-rights-of-data-principals/)
- [King Stubb & Kasiva: data retention and deletion under the DPDP Act](https://ksandk.com/data-protection-and-data-privacy/data-retention-deletion-dpdp-act-india/)
- [NALSAR Tech Law Forum: data retention under the DPDP framework](https://techlawforum.nalsar.ac.in/privacy-with-a-footnote-data-retention-under-the-dpdp-framework/)
- [S.S. Rana: MeitY plans to cut short the DPDP compliance timeline](https://ssrana.in/articles/meity-plans-to-cut-short-dpdp-compliance-timeline-and-notify-cross-border-restrictions-for-sdfs/)
- [Bar & Bench: MeitY notifies final DPDP Rules 2025](https://www.barandbench.com/view-point/meity-notifies-final-digital-personal-data-protection-rules-2025)
- [Gazette notification G.S.R. 846(E)](https://egazette.gov.in/WriteReadData/2025/267650.pdf)


## Owner/ops steps (not for implementers)

- Before fix wave p2-50 runs, trim FIX:SILENT-13 in the fix plan. It has not run yet: the worktree has no SchedulerJobStatus. Keep step 1 (module logger), step 2 (delete the two crashing cache jobs), step 3 (logger.exception in every wrapper) and the setdefault half of step 4. Drop the _persist_job_status half of step 4, step 5 (the SchedulerJobStatus model), step 6 (migration t4u5v6w7x8y9, whose id is already used by the engine's t4u5v6w7x8y9_add_research_engine_tables.py) and step 7 (the dashboard read from scheduler_job_status). Its test (b) then asserts only the in-memory _harvest_status entry. platform-jobruns provides the persisted history. If p2-50 has already run untrimmed, change nothing: platform-jobruns removes scheduler_job_status itself.
- Before any flag package builds, the integration lead merges the six flag mechanisms into platform-flags: data-flags and ai-flags (core/feature_flags.py), the money plan's core/feature_flags.py with require_flag, habit-flags (services/feature_flags.py and GET /api/v1/features) and ios-flags-be (config/feature_flags.py and GET /api/v1/app-config). Keep one module, one public flags endpoint and one iOS flags client. The endpoint can be GET /api/v1/flags or /api/v1/features, because the body shape {'flags': {...}} is the same. Their keys become FLAG_DEFAULTS entries with FEATURE_<KEY> env overrides, and a require_flag dependency can be added to the merged module. The non-flag app config of ios-flags-be (minimum build and App Store URL) can stay on /api/v1/app-config.
- In the App Store submission that first ships EventLogger (platform-ios-flags-events), update App Store Connect > App Privacy: Product Interaction, linked to the user, not used for tracking, purpose Analytics. Do this whatever the analytics flag state, so the binary's PrivacyInfo.xcprivacy and the label always agree.
- Turn on the 'analytics' flag in the admin Flags page only after the privacy policy (the owner text for FIX:FINSEC-09) names product analytics, its purpose and its retention period, and states that turning analytics off deletes the recorded events. Have legal approve the Home ask card's copy at the same time; it reuses the same purpose text.
- Have legal review docs/compliance/DPDP_RUNBOOK.md and the export's processor list: DeepSeek (PRC), Anthropic (USA), Apple APNs (USA) and the operations alert relay. Name the grievance contact and the response time. Confirm whether DeepSeek remains an acceptable processor for portfolio-related prompts.
- Decide the DPDP Rule 8(3) reading with legal and record it in the runbook's Decision line. Rule 8 applies from 13 May 2027 under G.S.R. 846(E), or earlier if MeitY's proposed shortening is notified; a 12-month window would mean 13 Nov 2026, so check the Gazette now. Under the narrow reading, keep USER_EVENTS_RETENTION_DAYS=180 and erase-on-withdrawal, as built. Under the broad reading, set USER_EVENTS_RETENTION_DAYS=365 in backend/.env and switch withdrawal to marking events withdrawn and excluding them from every query (a small code change described in the runbook). Either way, confirm that audit_log_entries and access logs are kept for at least one year, including rows of users erased under FIX:FINSEC-03.
- DPDP Rules 6 and 8(3) ask for logs to be kept for at least one year. Before the applicable date, either raise journald and logrotate retention (FIX:OPS-14 installs 'rotate 30') or ship logs to storage you control. Never purge audit_log_entries rows younger than one year.
- Set OPS_ALERT_WEBHOOK_URL in backend/.env on the server. Prefer a self-hosted ntfy server or an access-controlled ntfy topic: anyone who guesses a public ntfy.sh topic name can read it. Job failures, recoveries, canary failures and restore-drill failures then reach your phone, with scrubbed text of at most 300 characters.
- Set up the restore drill on the server. If Postgres is live, install postgresql-client matching the server's major version. Create an empty scratch database whose name contains 'drill' or 'scratch', for example createdb nivesh_restore_drill, owned by a role that can restore into it. Set RESTORE_DRILL_PG_URL in backend/.env. The code refuses any other name and any database named in DATABASE_URL or another *_DATABASE_URL. Run 'python scripts/restore_drill.py' once by hand and check the result on the admin Jobs page.
- After deploying the IST scheduler, run 'crontab -l' for the service user and confirm no job also runs from cron (the FIX:ML-03 note). On the first day, check on the admin Jobs page that bhavcopy ran at 19:00 IST, db_backup at 02:30 IST and model_canary at 08:30 IST.
- Make sure an is_admin account exists (FIX:AUTH-01: 'python scripts/manage_users.py set-admin <owner>') before using the new Flags, Jobs, Audit and Usage pages. After deploying, open them in a real browser and confirm the console shows no CSP violations; CSP cannot be unit-tested.
- Confirm the canary's model list (llm_utils DEEPSEEK_MODEL, HAIKU_MODEL and SONNET_MODEL) and that these DeepSeek and Anthropic model ids are current. If the engine's prose or other features use more model ids, add them to CANARY_EXTRA_MODELS. Set CANARY_ENABLED=0 in backend/.env only if all LLM spend must be zero.
- Cloud move (I48): approve or edit the trigger conditions in docs/codebase/CLOUD_MIGRATION.md. When a trigger is hit, choose the provider, an Indian region and a monthly budget, and provision managed Postgres with point-in-time recovery plus managed Redis.
- Orchestration note, not implementation work: during this revision, every tool call returned the session cost hook warning 'COST CRITICAL' (about $582 at the last report). Review spend before starting the build waves.
